# BGmi 硬链接工具

用于硬链接 BGmi 下载的新番资源，改善文件格式以便于自动化刮削，并且不会影响保种。

## 安装

1. 下载源码，解压
2. 配置 `config.py` 中的 `HARDLINK_DEST` 设置硬链接的目标目录。必须和 BGmi 配置的番剧下载
目录位于一个磁盘（对于 Docker 就是同一个数据卷）。

## 使用指南

完成配置后，使用 `python3 bgmi_hardlink_helper.py preview` 预览硬链接效果。若符合要求，则
可运行 `python3 bgmi_hardlink_helper.py run` 完成实际硬链接。硬链接后的文件可以随意重命名、
删除、移动。

如果需要配置 Crontab 任务定时硬链接，可以使用管理员权限运行
`python3 bgmi_hardlink_helper.py install_cron`。

## 进阶使用

### 配置番剧特殊规则

番剧特殊规则用于处理和刮削数据源不一致的情况。比如对于“小林家的龙女仆S”，TMDB 中没有单独条目，而是
对应“小林家的龙女仆”的“第2季。因此可以在 `config.py` 设置：

```python
MAP_RULE = {
    # 键值为 BGmi 显示的番名
    '小林家的龙女仆S': {
        # name 表示映射后的番名
        'name': '小林家的龙女仆',
        # season 表示对应的季名，参照刮削数据库填写
        'season': 2,
    },
}
```

若无配置，所有番剧默认为第 1 季。

### 配置目录格式

目录格式用于刮削器的自动识别，配置正确的话可以完全避免刮削。目前的配置适用于 Jellyfin 的刮削器，
理论上也可适用于绝大多数刮削器。

- 番剧存储于文件夹 `BANGUMI_FOLDER_FORMAT` 下。默认格式是 `{name}`，如“小林家的龙女仆”。
  也可以设置为嵌套，如 `{name}/Season {season}`，即“小林家的龙女仆/Season 2”。
- 番剧的命名格式为 `BANGUMI_FILE_FORMAT`，默认是 `S{season:0>2d}E{episode:0>2d}.{format}`。
  如“S01E01.mp4”。
