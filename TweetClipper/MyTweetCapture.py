from tweetcapture import TweetCapture
from selenium.webdriver.common.by import By
from asyncio import sleep, run
from tweetcapture.utils.webdriver import get_driver
from tweetcapture.utils.utils import is_valid_tweet_url, get_tweet_file_name, add_corners
from selenium.webdriver.common.by import By
from PIL import Image
from os import remove
from os.path import exists

class MyTweetCapture(TweetCapture):
    mode = 0
    radius = 0

    def __init__(self, mode=0, night_mode=0, test=False, show_parent_tweets=False, show_mentions_count=0, overwrite=True, radius=0):
        super().__init__(mode, night_mode, test, show_parent_tweets, show_mentions_count, overwrite, radius)

    def __code_main_footer_items_new(self, element, mode):
        XPATHS = [
            "((//ancestor::time)/..)[contains(@aria-describedby, 'id__')]/../../../..",
            ".//div[contains(@role, 'group')][not(contains(@id, 'id__'))]",
            ".//div[contains(@role, 'group')][contains(@id, 'id__')]",
            ".//div[contains(@data-testid, 'caret')]",
            "((//ancestor::span)/..)[contains(@role, 'button')]",
        ]
        hides = []
        if mode == 0:
            hides = [0,1,2,3,4]
        elif mode == 1:
            hides = [0,2,3,4]
        elif mode == 2:
            hides = [2,3,4]
        elif mode == 3:
            hides = [3,4]
        elif mode == 4:
            hides = [1,2,3,4]

        for i in hides:
            els = element.find_elements(By.XPATH, XPATHS[i])
            if len(els) > 0:
                for el in els:
                    element.parent.execute_script("""
                    arguments[0].style.display="none";
                    """, el)

        brdr = element.find_elements(By.XPATH, XPATHS[2])
        if len(brdr) == 1:
            element.parent.execute_script("""
            arguments[0].style.borderBottom="none";
            """, brdr[0])

    # Return: (elements, main_element_index)
    def __get_tweets(self, driver, show_parents, show_mentions_count):
        els = driver.find_elements(By.XPATH, "(//ancestor::article)/..")
        elements = []
        for element in els:
            if len(element.find_elements(By.XPATH, ".//article[contains(@data-testid, 'tweet')]")) > 0:
                elements.append(element)
        length = len(elements)
        if length > 0:
            if length == 1:
                return elements, 0
            else:
                main_element = -1
                for i, element in enumerate(elements):
                    main_tweet_details = element.find_elements(By.XPATH, ".//div[contains(@class, 'r-1471scf')]")
                    if len(main_tweet_details) == 1:
                        main_element = i
                        break
                if main_element == -1:
                    return [], -1
                else:
                    r = main_element+1
                    r2 = r+show_mentions_count
                    if show_parents and show_mentions_count > 0:
                        if len(elements[r:]) > show_mentions_count:
                            return (elements[0:r] + elements[r:r2]), main_element
                        return elements, main_element
                    elif show_parents:
                        if main_element == 0:
                            return elements[0:1], 0
                        else:
                            return elements[:r], main_element
                    elif show_mentions_count > 0:
                        if len(elements[r:]) > show_mentions_count:
                            return elements[main_element:1] + elements[r:r2], 0
                        return elements[main_element:], 0
                    else:
                        return elements[main_element:r], 0
        return [], -1

    def __hide_media(self, element, link_previews, photo, video, gif, quote):
        LINKPREVIEW_XPATH = ".//ancestor::div[@data-testid = 'card.layoutLarge.media']/ancestor::div[contains(@id, 'id__')][1]"
        MEDIA_XPATH = ".//ancestor::div[@data-testid = 'tweetPhoto']/ancestor::div[contains(@id, 'id__')]/div[1]"
        QUOTE_XPATH = ".//ancestor::div[contains(@class, 'r-desppf')]/ancestor::div[contains(@id, 'id__')][1]"
        # SEPARATOR_XPATH = ".//div[contains(@role, 'separator')]/.."
        BOTTOMBORDER_XPATH = ".//div[contains(@role, 'group')][not(contains(@id, 'id__'))]//following-sibling::div"

        media_elements = element.find_elements(By.XPATH, MEDIA_XPATH)

        # Remove annoying separator element ruining screenshot crops
        separator_elements = element.find_elements(By.XPATH, BOTTOMBORDER_XPATH)
        for separator_element in separator_elements:
            element.parent.execute_script("""
            arguments[0].style.border=0;
                """, separator_element)

        if link_previews is True:
            link_preview_elements = element.find_elements(By.XPATH, LINKPREVIEW_XPATH)
            for link_preview_element in link_preview_elements:
                element.parent.execute_script("""
                arguments[0].style.display="none";
                """, link_preview_element)
        if quote is True:
            quote_elements = element.find_elements(By.XPATH, QUOTE_XPATH)
            for quote_element in quote_elements:
                element.parent.execute_script("""
                arguments[0].style.display="none";
                """, quote_element)
        if len(media_elements) > 0:
            for el in media_elements:
                if video is True:
                    sel = el.find_elements(By.XPATH, ".//video[contains(@src, 'blob:')]")
                    if len(sel) > 0:
                        element.parent.execute_script("""
                        arguments[0].style.display="none";
                        """, el)
                        continue
                if gif is True:
                    sel = el.find_elements(By.XPATH, ".//video[not(contains(@src, 'blob:'))]")
                    if len(sel) > 0:
                        element.parent.execute_script("""
                        arguments[0].style.display="none";
                        """, el)
                        continue
                # if gif is True:
                #     sel = el.find_elements(By.XPATH, ".//video[not(contains(@src, 'blob:'))]")
                #     if len(sel) > 0:
                #         element.parent.execute_script("""
                #         arguments[0].style.display="none";
                #         """, el)
                #         continue
                if photo is True:
                    sel = el.find_elements(By.XPATH, ".//div[contains(@data-testid, 'videoPlayer')]")
                    if len(sel) == 0:
                        element.parent.execute_script("""
                        arguments[0].style.display="none";
                        """, el)
                        continue

    def __hide_global_items(self, driver):
        HIDE_ITEMS_XPATH = ['/html/body/div/div/div/div[1]',
        '/html/body/div/div/div/div[2]/header', '/html/body/div/div/div/div[2]/main/div/div/div/div/div/div[1]']
        for item in HIDE_ITEMS_XPATH:
            try:
                element = driver.find_element(By.XPATH, item)
                driver.execute_script("""
                arguments[0].style.display="none";
                """, element)
            except:
                continue

    def __margin_tweet(self, mode, base):
        if mode == 0 or mode == 1:
            try:
                base.parent.execute_script(
                    """arguments[0].childNodes[0].style.paddingBottom = '35px';""", base.find_element(By.TAG_NAME, "article"))
            except:
                pass

    def __code_footer_items(self, mode):
        if mode == 0 or mode == 4:
            return """
            arguments[0].style.display="none";
            arguments[1].style.display="none";
            """
        else:
            return """
            arguments[1].style.display="none";
            """

    def __increase_font_size(self, element):
        TWEETTEXT_XPATH = ".//div[contains(@data-testid, 'tweetText')]"
        tweet_text_elements = element.find_elements(By.XPATH, TWEETTEXT_XPATH)
        for tweet_text_element in tweet_text_elements:
            element.parent.execute_script("""
            arguments[0].style.fontSize="20px";
                """, tweet_text_element)
            element.parent.execute_script("""
            arguments[0].style.lineHeight="25px";
                """, tweet_text_element)

    async def screenshot(self, url, path=None, mode=None, night_mode=None, show_parent_tweets=None, show_mentions_count=None, overwrite=None, radius=None):
        if is_valid_tweet_url(url) is False:
            raise Exception("Invalid tweet url")

        if not isinstance(path, str) or len(path) == 0:
            path = get_tweet_file_name(url)

        if exists(path) and (self.overwrite if overwrite is None else overwrite) is False:
            raise Exception("File already exists")

        url = is_valid_tweet_url(url)
        if self.lang:
            url += "?lang=" + self.lang

        driver = self.driver
        radius = self.radius if radius is None else radius
        try:
            driver.get(url)
            driver.delete_all_cookies()
            driver.add_cookie(
                {"name": "night_mode", "value": str(self.night_mode if night_mode is None else night_mode)})
            driver.get(url)
            await sleep(self.wait_time)

            self.__hide_global_items(driver)
            driver.execute_script("!!document.activeElement ? document.activeElement.blur() : 0")

            if self.test is True:
                driver.save_screenshot(f"web{self.__web}.png")
                self.__web += 1
            await sleep(2.0)
            elements, main = self.__get_tweets(driver, self.show_parent_tweets if show_parent_tweets is None else show_parent_tweets, self.show_mentions_count if show_mentions_count is None else show_mentions_count)
            if len(elements) == 0:
                raise Exception("Tweets not found")
            else:
                for i, element in enumerate(elements):
                    if i == main:
                        self.__code_main_footer_items_new(element, self.mode if mode is None else mode)
                    else:
                        try:
                            driver.execute_script(self.__code_footer_items(self.mode if mode is None else mode), element.find_element(By.CSS_SELECTOR, "div.r-1ta3fxp"), element.find_element(By.CSS_SELECTOR, ".r-1hdv0qi:first-of-type"))
                        except:
                            pass
                    self.__increase_font_size(element)
                    self.__hide_media(element, self.hide_link_previews, self.hide_photos, self.hide_videos, self.hide_gifs, self.hide_quotes)
                    if i == len(elements)-1:
                        self.__margin_tweet(self.mode if mode is None else mode, element)

            if len(elements) == 1:
                elements[0].screenshot(path)
                if radius > 0:
                    im = Image.open(path)
                    im = add_corners(im, radius)
                    im.save(path)
                    # ret_im = im
                    # remove(path)
            else:
                filenames = []
                for element in elements:
                    filename = "tmp_%s_tweetcapture.png" % element.id
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    await sleep(0.1)
                    element.screenshot(filename)
                    filenames.append(filename)
                width = 0
                height = 0
                images = []
                for filename in filenames:
                    im = Image.open(filename)
                    if width == 0:
                        width = im.size[0]
                    height += im.size[1]
                    images.append(im)
                c = (255,255,255)
                if self.night_mode == 1:
                    c = (21,32,43)
                elif self.night_mode == 2:
                    c = (0,0,0)
                new_im = Image.new('RGB', (width,height), c)
                y = 0
                for im in images:
                    new_im.paste(im, (0,y))
                    y += im.size[1]
                    im.close()
                    remove(im.filename)

                if radius > 0:
                    new_im = add_corners(new_im, self.radius)
                new_im.save(path)
                new_im.close()
                # ret_im = new_im
                # remove(path)
            # driver.quit()

        except Exception as err:
            # driver.quit()
            self.close_driver()
            raise err
        return path
        # return ret_im

    async def start_driver(self):
        self.driver = await get_driver(self.chrome_opts, self.driver_path, self.gui)

    def close_driver(self):
        self.driver.quit()



if __name__ == '__main__':

    tweet = MyTweetCapture()
    run(tweet.start_driver())
    tweet.hide_all_media()

    while True:
        link = input('Enter tweet link: ')
        night_mode = int(input('Enter night mode: '))
        mode = int(input('Enter mode: '))
        save_as = input('Enter file name to save screenshot: ')
        to_exit = input('Should exit [y/n]: ')

        run(tweet.screenshot(
                f"{link}", f"{save_as}", mode=mode, night_mode=night_mode))

        if to_exit == 'y':
            break

    tweet.close_driver()
