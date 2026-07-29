import httpx
import asyncio

async def scan_ragflow():
    # 你的真实 API KEY
    API_KEY = "ragflow-y5RsobHrUDUeqcfff12UDJj6jb_rbNUoEYDDOaT-o8Q"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 我们穷举了 RAGFlow 历史上出现过的所有坑爹路径和请求方式
    test_cases = [
        # 1. 最新官方版标准 GET
        ("GET", "http://192.168.244.1/api/v1/api/new_conversation?user_id=123", None),
        # 2. 某些旧版本的 GET
        ("GET", "http://192.168.244.1/v1/api/new_conversation?user_id=123", None),
        # 3. 某些版本要求用 POST 创建对话
        ("POST", "http://192.168.244.1/api/v1/api/new_conversation", {"user_id": "123"}),
        # 4. OpenAI 兼容接口直连（RAGFlow 0.10+ 最新特性）
        ("POST", "http://192.168.244.1/v1/chat/completions", {
            "model": "ragflow-chat",
            "messages": [{"role": "user", "content": "你好"}],
            "stream": False
        }),
        # 5. 加上 api 前缀的 OpenAI 接口
        ("POST", "http://192.168.244.1/api/v1/chat/completions", {
            "model": "ragflow-chat",
            "messages": [{"role": "user", "content": "你好"}],
            "stream": False
        })
    ]

    print("🔍 启动 RAGFlow 接口究极扫描仪...\n" + "="*50)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for method, url, payload in test_cases:
            print(f"👉 正在探测: [{method}] {url}")
            try:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                else:
                    resp = await client.post(url, headers=headers, json=payload)
                
                print(f"   状态码: {resp.status_code}")
                print(f"   返回值: {resp.text[:300]}") # 只打印前300个字符防刷屏
                
                if resp.status_code == 200:
                    print("   🎉🎉🎉 找到了！这个接口是通的！")
                elif resp.status_code == 401:
                    print("   ⚠️ 401 Unauthorized：接口存在，但 API Key 权限不对或失效！")
                elif resp.status_code == 404:
                    print("   ❌ 404 Not Found：接口不存在。")
                elif resp.status_code == 405:
                    print("   ❌ 405 Method Not Allowed：接口存在，但不能用这个方法（比如该用GET你用了POST）。")
                print("-" * 50)
                
            except Exception as e:
                print(f"   💥 请求崩溃: {str(e)}")
                print("-" * 50)

if __name__ == "__main__":
    asyncio.run(scan_ragflow())
