from Browser import *

async def querySearch(query: str,num=10) -> str:
    """
    查询搜索结果
    :param query: 搜索关键词
    :return: 搜索结果HTML字符串
    """
    query = query.replace(" ", "+")
    browser = Browser()
    await browser.init_browser()
    await browser.goto(page_id="search", url=f"https://www.sogou.com/web?query={query}")
    divs = await browser.wait_for_elements(selector="//div[contains(@class,'vrwrap')]", page_id="search", timeout=10000)
    text = ''
    items = []
    i = 0
    for div in divs:
        try:
            a_list = await div.locator("a").all()
            a_first = a_list[0]  
            a = div.find_element(By.XPATH, ".//a")
            title = a.text
            url = a.get_attribute("href")
            summaryDiv = div.find_element(By.XPATH, ".//*[contains(@class,'space-txt') or contains(@class,'img-text__content') or contains(@class,'summary')]")
            summary = summaryDiv.text
            items.append({"title":title,"url":url,"summary":summary})
            i += 1
            text += f"【结果{i}】\n"
            text += f"标题：{title}\n"
            text += f"链接：{url}\n"
            text += f"摘要：{summary}\n"
            text += "\n"            
        except Exception as e:
            pass   
    
    await browser.close()
    return 

if __name__ == "__main__":
    asyncio.run(querySearch("你好"))
   