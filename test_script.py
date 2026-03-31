import websockets

connect_kwargs = {
    "ping_interval": 20,
    "ping_timeout": 10,
    # 限制单条消息最大为 10MB，防止异常数据占用过多内存
    "max_size": 10 * 1024 * 1024,
    "proxy":"http://127.0.0.1:7890"
}

url = "wss://testnet.binance.vision/ws"

ws = await websockets.connect(url, **connect_kwargs)
print(ws)