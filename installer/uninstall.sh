#!/bin/bash

CHATBI_BASE=/opt

read -r -p "即将卸载 ChatBI 服务，包括删除运行目录、数据及相关镜像，是否继续? [Y/n] " input

case $input in
   [yY][eE][sS]|[yY])
      echo "Yes"
      ;;
   [nN][oO]|[nN])
      echo "No"
      exit 1
      ;;
   *)
      echo "无效输入..."
      exit 1
      ;;
esac

echo "停止 ChatBI 服务"
sctl stop >/dev/null 2>&1

if [ -f /usr/bin/sctl ]; then
   # 获取已安装的 ChatBI 的运行目录
   CHATBI_BASE=$(grep "^CHATBI_BASE=" /usr/bin/sctl | cut -d'=' -f2)
fi

# 清理 ChatBI 相关镜像
if test ! -z "$(docker images -f dangling=true -q)"; then
   echo "清理虚悬镜像"
   docker rmi $(docker images -f dangling=true -q)
fi

if test -n "$(docker images | grep 'chatbi/chatbi')"; then
   echo "清理 ChatBI 镜像"
   docker rmi $(docker images | grep "chatbi/chatbi" | awk -F' ' '{print $1":"$2}')
fi

# 清理 ChatBI 运行目录及命令行工具 sctl
rm -rf ${CHATBI_BASE}/chatbi /usr/bin/sctl

echo "ChatBI 服务卸载完成"
