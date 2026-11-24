# 收发边界（按需）

1. 核接口：stream、datagram/record 或已分帧 SDK；不重复组帧。
2. 流读保留 header/payload 残余与后帧，完整校验才交付；一次 recv 不保证一帧。写按实际字节推进 offset，不重发前缀；按 API 重试，无进展等待、不忙轮询。
3. 非零请求的 stream recv=0 仅表示接收 EOF，残帧截断；datagram 空包也可为 0。`MSG_TRUNC` 等截断不能下次 recv 拼回；上层分片依协议，无法判截断留缺口。
4. 分配/复制/header+payload 计算前核端序、长度上限、溢出；限制缓冲/队列/在途量并背压。坏长度仅按协议拒绝/关闭或有界重同步。部分 I/O 不刷新 deadline；取消重连不混会话。
5. 原 runner 测分片/合帧、尾部 EOF、部分写、超长、空/截断包、消费停滞、取消重连；独立期望与实际字节/返回值/交付帧留证。host socketpair 或项目 seam 不证明 MCU/链路/HIL。

依据：[Python stream I/O](https://docs.python.org/3.12/howto/sockets.html#using-a-socket)、[Linux recv](https://man7.org/linux/man-pages/man2/recv.2.html)。
