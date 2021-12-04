# rclonectl

对 Rclone 的包装，旨在更加优雅的使用 Rclone。

## 功能特点

Rclonectl 可以管理挂载点（FUSE）与服务（Webdav、FTP 等），监测上传状况，采用类似 systemctl 的交互模式，更加友好。目标是实现 Rclone 的统一管理命令行界面。

- 单文件，纯标准库实现
- 单个 Rclone 实例
- 可以被 systemd 用户模式管理启动

## 使用示例

### 管理后台

```
rclonectl.py rcd {start,stop}
```

### 管理服务

* WebDav 服务（目前只支持 WebDav）
  ```
  ./rclonectl.py unit {start,stop} my-webdav
  ```

* 文件系统挂载 （TBD）
  ```
  ./rclonectl.py unit {start,stop} custom-mount
  ```


