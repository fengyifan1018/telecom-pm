"""企业微信智能机器人长连接客户端（独立进程，勿并入 uvicorn——同一机器人仅允许一个有效连接）。

职责：
1. 经官方 SDK 建立长连接（BotID/Secret 鉴权，自动重连/心跳）
2. 周期消费 outbox（notifications.push_status=pending）主动推送给收件人
未配置 WECHAT_BOT_ID 时进程直接退出（compose 中该服务可选启用）。
"""
import asyncio
import logging
import os

from app.services import wecom_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wecom_client")


async def main() -> None:
    bot_id = os.getenv("WECHAT_BOT_ID", "")
    if not bot_id:
        logger.warning("WECHAT_BOT_ID 未配置，企微推送关闭。")
        return
    from aibot import WSClient, WSClientOptions

    client = WSClient(WSClientOptions(
        bot_id=bot_id,
        secret=os.getenv("WECHAT_BOT_SECRET", ""),
    ))
    _client_holder["client"] = client

    @client.on("connected")
    async def _on_connected(*_):
        logger.info("wecom long connection established")

    @client.on("message.text")
    async def _on_text(frame):
        # 用户给机器人发消息（满足"先发过消息才能被推送"的前置），暂不做对话处理
        logger.info("received user message (silent ack)")

    await client.connect()
    logger.info("wecom push loop started")
    while True:
        try:
            async with asyncio.timeout(60):
                pass
        except TimeoutError:
            pass
        if _client_holder.get("client") is None:
            return
        try:
            from app.database import async_session
            async with async_session() as db:
                n = await wecom_service.push_pending(db, sender=client.send_message)
                if n:
                    logger.info("pushed %s notifications", n)
        except Exception:  # noqa: BLE001 断连/DB 波动，SDK 自动重连后下轮继续
            logger.exception("push loop iteration failed")
        await asyncio.sleep(15)


_client_holder: dict = {}


def get_client():
    """供 push_pending 未注入 sender 时使用（长连接进程内）。"""
    return _client_holder.get("client")


if __name__ == "__main__":
    asyncio.run(main())
