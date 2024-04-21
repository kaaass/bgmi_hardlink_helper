from unittest import TestCase

from bgmi_hardlink_helper import *


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
            self.assertEqual(case['expect'], extract_season_from_bgmi({'bangumi_name': case['name']}))
