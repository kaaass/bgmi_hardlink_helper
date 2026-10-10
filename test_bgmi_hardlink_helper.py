import os
from unittest import TestCase, skipUnless
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path

import bgmi_hardlink_helper as helper

if helper._BGMI_V5:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from bgmi.lib import table
else:
    import peewee
    from bgmi.lib import models

from bgmi_hardlink_helper import extract_season_from_bgmi


class Test(TestCase):
    def test_extract_season_from_bgmi(self):
        cases = [
            {
                'name': '孤独摇滚',
                'expect': {
                    'name': '孤独摇滚',
                    'season': 1
                }
            },
            {
                'name': '我立于百万生命之上 第二季',
                'expect': {
                    'name': '我立于百万生命之上',
                    'season': 2
                }
            },
            {
                'name': '约会大作战 第五季',
                'expect': {
                    'name': '约会大作战',
                    'season': 5
                }
            },
            {
                'name': 'Love Live! 虹咲学园学园偶像同好会 第2季',
                'expect': {
                    'name': 'Love Live! 虹咲学园学园偶像同好会',
                    'season': 2
                }
            },
            {
                'name': '为美好的世界献上祝福！第三季',
                'expect': {
                    'name': '为美好的世界献上祝福！',
                    'season': 3
                }
            },
        ]

        for case in cases:
            expected = dict(case['expect'], ep_offset=None)
            self.assertEqual(expected, extract_season_from_bgmi({'bangumi_name': case['name']}))

    def test_sanitize_bangumi_name(self):
        name = 'A/B\\C:D?E*F<G>H|I"J'
        expected_name = 'A／B＼C：D？E＊F＜G＞H｜I＂J'
        with patch.object(helper, 'MAP_RULE', {}):
            info = extract_season_from_bgmi({'bangumi_name': name + ' 第二季'})
            self.assertEqual(info, {'name': expected_name, 'season': 2, 'ep_offset': None})
        with patch.object(helper, 'MAP_RULE', {
            'original': {'name': name, 'season': 3, 'ep_offset': -12},
        }):
            info = extract_season_from_bgmi({'bangumi_name': 'original'})
            self.assertEqual(info, {'name': expected_name, 'season': 3, 'ep_offset': -12})

    def test_destination_rules_ignore_bgmi_v5_metadata(self):
        data = {
            'bangumi_name': 'original 第二季', 'season': 4,
            'display_name': 'display', 'episode_offset': -12,
        }
        with patch.object(helper, 'MAP_RULE', {}):
            self.assertEqual(extract_season_from_bgmi(data), {
                'name': 'original', 'season': 2, 'ep_offset': None,
            })
            self.assertEqual(extract_season_from_bgmi(dict(data, display_name='')), {
                'name': 'original', 'season': 2, 'ep_offset': None,
            })
        with patch.object(helper, 'MAP_RULE', {
            data['bangumi_name']: {'name': 'mapped', 'season': 3, 'ep_offset': 24},
        }):
            self.assertEqual(extract_season_from_bgmi(data), {
                'name': 'mapped', 'season': 3, 'ep_offset': 24,
            })
        with patch.object(helper, 'MAP_RULE', {
            data['bangumi_name']: {'name': 'mapped', 'season': 3},
        }):
            self.assertEqual(extract_season_from_bgmi(data), {
                'name': 'mapped', 'season': 3, 'ep_offset': None,
            })

    def test_episode_offset_in_link_path(self):
        cases = [
            ([57, 56], -55, [2, 1]),
            ([56, 55], -55, [56, 55]),
            ([56, 1], -55, [56, 1]),
            ([1, 2], 24, [25, 26]),
            ([1, 2], 0, [1, 2]),
            ([1, 2], None, [1, 2]),
            ([0, 1], None, [0, 1]),
            ([], -55, []),
        ]
        for episodes, offset, expected in cases:
            with self.subTest(episodes=episodes, offset=offset), TemporaryDirectory() as dest:
                rule = {'name': 'A/B', 'season': 2}
                if offset is not None:
                    rule['ep_offset'] = offset
                player_data = {episode: {'path': f'/video{episode}.mkv'} for episode in episodes}
                if helper._BGMI_V5:
                    followed = helper.Followed(
                        bangumi_name='original', episodes=set(episodes), season=1,
                        episode_offset=0, display_name='',
                    )
                    data = [(followed, None)]
                else:
                    data = [{'bangumi_name': 'original'}]
                with patch.multiple(helper,
                                    MAP_RULE={'original': rule},
                                    HARDLINK_DEST=dest,
                                    BANGUMI_FOLDER_FORMAT='{name}/Season {season}',
                                    BANGUMI_FILE_FORMAT='S{season:02d}E{episode:02d}.{format}'), \
                        patch.object(helper.Followed, 'get_all_followed', return_value=data), \
                        patch.object(helper, 'get_player', return_value=player_data) as player, \
                        patch.object(helper.os, 'link') as link, \
                        patch('builtins.print'):
                    helper.run_hardlink()
                    if helper._BGMI_V5:
                        player.assert_called_once_with(
                            'original', episodes=set(episodes), season=1,
                            episode_offset=0, display_name='',
                        )
                    else:
                        player.assert_called_once_with('original')
                    self.assertEqual(link.call_count, len(episodes))
                    for call, episode, adjusted in zip(link.call_args_list, episodes, expected):
                        source, target = call.args
                        self.assertEqual(source, os.path.join(helper.save_path, f'video{episode}.mkv'))
                        self.assertEqual(
                            os.path.normpath(target),
                            os.path.join(dest, 'A／B', 'Season 2', f'S02E{adjusted:02d}.mkv'),
                        )

    @skipUnless(helper._BGMI_V5, '仅验证 BGmi v5 接口')
    def test_bgmi_v5_database_and_video_paths(self):
        for formatted, rules, legacy_subscription in [(False, {}, False), (True, {}, False), (True, {
            'original': {'name': 'mapped', 'season': 3, 'ep_offset': -54},
        }, False), (True, {'original': {'name': 'mapped', 'season': 3}}, False),
            (False, {}, True)]:
            with self.subTest(formatted=formatted, rules=rules, legacy_subscription=legacy_subscription), TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / 'downloads'
                dest = root / 'library'
                video = source / ('display/Season 2/S02E01.mkv' if formatted else 'original/56/video.mkv')
                video.parent.mkdir(parents=True)
                video.write_bytes(b'video')
                engine = create_engine('sqlite://')
                table.Base.metadata.create_all(engine)
                session = sessionmaker(engine, expire_on_commit=False)
                try:
                    with session.begin() as tx:
                        for name, status, bangumi_status in [
                            ('original', table.Followed.STATUS_FOLLOWED, table.Bangumi.STATUS_UPDATING),
                            ('deleted', table.Followed.STATUS_DELETED, table.Bangumi.STATUS_UPDATING),
                            ('ended', table.Followed.STATUS_END, table.Bangumi.STATUS_END),
                        ]:
                            tx.add(table.Bangumi(id=name, name=name, status=bangumi_status))
                            metadata = {} if legacy_subscription else dict(
                                season=2, episode_offset=-55, display_name='display',
                            )
                            tx.add(table.Followed(
                                bangumi_name=name, status=status, episodes={56, 57},
                                **metadata,
                            ))
                    with patch.object(table, 'Session', session), \
                            patch.multiple(helper.bgmi_config.cfg, save_path=source,
                                           enable_path_formatter=formatted,
                                           path_formatter='{name}/Season {season}/S{season:02d}E{episode:02d}{suffix}'), \
                            patch.multiple(helper, save_path=source, HARDLINK_DEST=str(dest), MAP_RULE=rules,
                                           BANGUMI_FOLDER_FORMAT='{name}/Season {season}',
                                           BANGUMI_FILE_FORMAT='S{season:02d}E{episode:02d}.{format}'), \
                            patch('builtins.print') as output:
                        name, season, episode = ('mapped', 3, 56 + rules['original'].get('ep_offset', 0)) if rules else ('original', 1, 56)
                        target = dest / name / f'Season {season}' / f'S{season:02d}E{episode:02d}.mkv'
                        helper.run_hardlink(preview=True)
                        self.assertFalse(target.exists())
                        previews = [call.args for call in output.call_args_list
                                    if len(call.args) == 3 and call.args[1] == '-->']
                        self.assertEqual(len(previews), 1)
                        self.assertEqual(os.path.normpath(previews[0][0]), str(video))
                        self.assertEqual(os.path.normpath(previews[0][2]), str(target))
                        helper.run_hardlink()
                        self.assertTrue(os.path.samefile(video, target))
                        self.assertEqual(list(dest.rglob('*.mkv')), [target])
                        helper.run_hardlink()
                        output.assert_any_call('共链接', 0, '个文件')
                finally:
                    engine.dispose()

    @skipUnless(not helper._BGMI_V5, '仅验证旧版 BGmi 接口')
    def test_legacy_database_and_video_paths(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'downloads'
            dest = root / 'library'
            video = source / 'original 第二季' / '1' / 'video.mkv'
            video.parent.mkdir(parents=True)
            video.write_bytes(b'video')
            db = peewee.SqliteDatabase(':memory:')
            try:
                with db.bind_ctx([models.Bangumi, models.Followed]):
                    db.create_tables([models.Bangumi, models.Followed])
                    for name, status, bangumi_status in [
                        ('original 第二季', models.STATUS_FOLLOWED, models.STATUS_UPDATING),
                        ('deleted', models.STATUS_DELETED, models.STATUS_UPDATING),
                        ('ended', models.STATUS_FOLLOWED, models.STATUS_END),
                    ]:
                        models.Bangumi.create(name=name, subtitle_group='', keyword='',
                                             update_time='Mon', cover='', status=bangumi_status)
                        models.Followed.create(bangumi_name=name, status=status)
                    with patch.object(helper.bgmi_config.cfg, 'save_path', source), \
                            patch.multiple(helper, save_path=source, HARDLINK_DEST=str(dest), MAP_RULE={},
                                           BANGUMI_FOLDER_FORMAT='{name}/Season {season}',
                                           BANGUMI_FILE_FORMAT='S{season:02d}E{episode:02d}.{format}'), \
                            patch('builtins.print') as output:
                        target = dest / 'original' / 'Season 2' / 'S02E01.mkv'
                        helper.run_hardlink(preview=True)
                        self.assertFalse(target.exists())
                        previews = [call.args for call in output.call_args_list
                                    if len(call.args) == 3 and call.args[1] == '-->']
                        self.assertEqual(len(previews), 1)
                        self.assertEqual(os.path.normpath(previews[0][0]), str(video))
                        self.assertEqual(os.path.normpath(previews[0][2]), str(target))
                        helper.run_hardlink()
                        self.assertTrue(os.path.samefile(video, target))
                        self.assertEqual(list(dest.rglob('*.mkv')), [target])
                        helper.run_hardlink()
                        output.assert_any_call('共链接', 0, '个文件')
            finally:
                db.close()
