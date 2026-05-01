import asyncio
import json
import os
from typing import Optional,Dict
from playwright.async_api import BrowserContext, Page, async_playwright, Playwright
from HotReloadConfig import config
from threading import Lock

class Browser:
    _instance: Optional["Browser"] = None
    _lock = Lock()

    #后面要同步运行多个浏览器 不使用单例模式
    # def __new__(cls, *args, **kwargs):
    #     with cls._lock:
    #         if cls._instance is None:
    #             cls._instance = super().__new__(cls)
    #     return cls._instance

    def __init__(self, 
                 headless: bool = config.browser.headless,
                 remote_mode: bool = config.browser.remote_mode,
                 remote_cdp: str = config.browser.remote_cdp_endpoint):
        
        if "_initialized" in self.__dict__:
            return
        
        # 固定配置
        self.headless = headless
        self.remote_mode = remote_mode
        self.remote_cdp = remote_cdp
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        
        # 核心修复：用字典管理多个页面
        self._pages: Dict[str, Page] = {}  
        self._default_page_id = "default"
        self._closed = False
        self._initialized = True

    async def init_browser(self):
        """初始化浏览器"""
        self._playwright = await async_playwright().start()
        
        # 启动/连接浏览器
        if self.remote_mode:
            self._browser = await self._playwright.chromium.connect_over_cdp(self.remote_cdp)
        else:
            self._browser = await self._playwright.chromium.launch(headless=self.headless,args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        
        # 创建上下文
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=self.user_agent
        )
        
        # 创建默认页面并保存
        self._page = await self._context.new_page()
        self._pages[self._default_page_id] = self._page

    # ================================= 多页面核心方法
    async def new_page(self, page_id: str, url: Optional[str] = None) -> Page:
        """创建一个带唯一标识的新页面（支持多页面）"""
        if page_id in self._pages:
            return self._pages[page_id]
        
        new_p = await self._context.new_page()
        self._pages[page_id] = new_p
        
        if url:
            await new_p.goto(url, wait_until="domcontentloaded")
        return new_p

    def get_page(self, page_id: str = None) -> Page:
        """获取指定页面，不填则使用默认页面"""
        if page_id is None or page_id not in self._pages:
            return self._pages[self._default_page_id]
        return self._pages[page_id]

    async def close_page(self, page_id: str):
        """关闭指定页面"""
        if page_id in self._pages:
            await self._pages[page_id].close()
            del self._pages[page_id]

    # ================================= 业务方法（支持多页面）
    async def goto(self, url: str, page_id: str = None, timeout: float = 20000):
        page = self.get_page(page_id)
        page.set_default_navigation_timeout(timeout)
        try:
            await page.goto(url, wait_until="domcontentloaded")
        except Exception:
            await page.evaluate("window.stop()")
            raise

    async def scroll(self, to_pos: int = 100000, page_id: str = None):
        page = self.get_page(page_id)
        await page.evaluate(f"document.documentElement.scrollTop = {to_pos}")

    async def click_node(self, selector, page_id: str = None):
        page = self.get_page(page_id)
        loc = page.locator(selector)
        await loc.first.click()

    async def wait_for_elements(self, selector: str, page_id: str = None, timeout: float = 10000):
        page = self.get_page(page_id)
        loc = page.locator(selector)
        try:
            await loc.first.wait_for(timeout=timeout)
        except:
            print(f"等待元素 {selector} 超时")
            return []
        return await loc.all()

    # ================================= cookie 不变
    async def save_cookie(self, path: str):
        cookies = await self._context.cookies()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

    async def load_cookie(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            cookies = json.load(f)
        valid = [c for c in cookies if c.get("sameSite") in ("Strict", "Lax", "None")]
        await self._context.add_cookies(valid)

    async def get_page_html(self, page_id: str = None) -> str:
        """
        获取指定页面的完整 HTML
        :param page_id: 页面ID，不填则使用默认页面
        :return: 页面HTML字符串
        """
        page = self.get_page(page_id)
        return await page.content()

    async def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            # 关闭所有页面
            for p in self._pages.values():
                await p.close()
            await self._context.close()
            if not self.remote_mode:
                await self._browser.close()
            await self._playwright.stop()
        except Exception:
            pass



if __name__ == "__main__":
    # 测试主函数
    async def main():
        # 1. 创建浏览器单例（只启动一次）
        browser = Browser()
        await browser.init_browser()
        print("✅ 浏览器启动完成")
        # 2. 创建两个独立页面，同时打开，互不干扰
        # 页面1：小红书
        await browser.new_page("xiaohong", "https://www.xiaohongshu.com/")
        print("✅ 小红书页面已在后台打开")
        # 页面2：百度
        await browser.new_page("baidu", "https://www.baidu.com/")
        print("✅ 百度页面已在后台打开")

        # =============================================
        # 3. 分别操作两个页面（核心：不切前台、不抢窗口）
        # =============================================

        # 给小红书下滑
        print("🔽 小红书开始下滑...")
        await browser.scroll(page_id="xiaohong")

        # 给百度下滑
        print("🔽 百度开始下滑...")
        await browser.scroll(page_id="baidu")

        print("🎉 两个页面同时操作完成！全程没有切页、没有跳转！")

        # 最后关闭
        await asyncio.sleep(20)
        await browser.close()
    asyncio.run(main())