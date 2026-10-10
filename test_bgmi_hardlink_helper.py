import os
from unittest import TestCase
from unittest.mock import patch
from tempfile import TemporaryDirectory

import bgmi_hardlink_helper as helper

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
                with patch.multiple(helper,
                                    MAP_RULE={'original': rule},
                                    HARDLINK_DEST=dest,
                                    BANGUMI_FOLDER_FORMAT='{name}/Season {season}',
                                    BANGUMI_FILE_FORMAT='S{season:02d}E{episode:02d}.{format}'), \
                        patch.object(helper.Followed, 'get_all_followed', return_value=[{'bangumi_name': 'original'}]), \
                        patch.object(helper, 'get_player', return_value=player_data) as player, \
                        patch.object(helper.os, 'link') as link, \
                        patch('builtins.print'):
                    helper.run_hardlink()
                    player.assert_called_once_with('original')
                    self.assertEqual(link.call_count, len(episodes))
                    for call, episode, adjusted in zip(link.call_args_list, episodes, expected):
                        source, target = call.args
                        self.assertEqual(source, os.path.join(helper.save_path, f'video{episode}.mkv'))
                        self.assertEqual(
                            os.path.normpath(target),
                            os.path.join(dest, 'A／B', 'Season 2', f'S02E{adjusted:02d}.mkv'),
                        )
