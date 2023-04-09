import json
import tweepy
import requests
import m3u8
import subprocess
from MyTweetCapture import MyTweetCapture
from ImageUtils import ImageUtils
from asyncio import run
from datetime import datetime
from os import remove
from os.path import isfile
from PIL import Image
from moviepy.editor import ImageClip, clips_array, VideoFileClip
import logging

class TweetClipper:

    __size = 'medium'
    __prefix_url = 'https://video.twimg.com'

    def __init__(self, keys_file):
        """
        Initialize a TweetClipper instance

        Args:
            keys_file (str): path to json file containing twitter api v2 keys with read and write access enabled
        """
        with open(keys_file) as k:
            auth_keys = json.loads(k.read())

        self.__api_client = tweepy.Client(bearer_token=auth_keys['bearer_token'], access_token=auth_keys['access_token'], access_token_secret=auth_keys['access_token_secret'], consumer_key=auth_keys['consumer_key'], consumer_secret=auth_keys['consumer_secret'], return_type=dict, wait_on_rate_limit=True)

        self.__screenshoter = MyTweetCapture()
        run(self.__screenshoter.start_driver())
        self.__screenshoter.hide_all_media()

    def __get_tweet(self, tweet_id, size=None):
        """
        Download and save media (video/gif) from tweet

        Args:
            tweet_id (str): Tweet to download video from
            size (str): Size of video to download (small, medium or large)
        """
        if size is None:
            size = self.__size

        client = self.__api_client
        expansions = 'attachments.media_keys,author_id,referenced_tweets.id.author_id'
        media_fields = 'variants'
        tweet_fields='created_at'
        tweet = client.get_tweet(
            tweet_id, expansions=expansions, media_fields=media_fields, tweet_fields=tweet_fields)

        username = tweet.get('includes').get('users')[0].get('username')
        tweet_time = tweet.get('data').get('created_at')

        variants = None
        expanded_media = tweet.get('includes').get('media')
        if expanded_media is None:
            return None

        for media in expanded_media:
            if media.get('type') == 'video' or media.get('type') == 'animated_gif':
                variants = media.get('variants')
                media_type = media.get('type')
                break

        if variants is None:
            raise RuntimeError(f'{tweet_id}: Tweet does not have video or gif attachment')
            # return None

        if media_type == 'video':
            video_path = self.__download_video(variants, tweet_id, size)
        if media_type == 'animated_gif':
            video_path = self.__download_gif(variants, tweet_id)

        return {'username': username, 'time': tweet_time, 'video_path' : video_path}

    def __download_video(self, variants, tweet_id, size):
        """
        Download and save video attachment from tweet

        Args:
            variants (list): list of variant stream playlists available for download
            tweet_id (str): Tweet to download video from
            size (str): Preferred size of video to download
        """
        for item in variants:
            if item['content_type'] == 'application/x-mpegURL':
                stream_url = item['url']
                break

        r = requests.get(stream_url)
        m3u8_master = m3u8.loads(r.text)
        playlists = m3u8_master.data['playlists']

        bandwidths = []
        for playlist in playlists:
            bandwidths.append(playlist['stream_info']['average_bandwidth'])

        bandwidths = sorted(bandwidths)

        if size == 'small':
            bandwidth_size = bandwidths[0]
        elif size == 'large':
            bandwidth_size = bandwidths[-1]
        else:
            bandwidth_size = bandwidths[len(bandwidths) // 2]

        for playlist in playlists:
            if playlist['stream_info']['average_bandwidth'] == bandwidth_size:
                stream_uri = playlist['uri']
                break

        stream_uri = self.__prefix_url + stream_uri

        r = requests.get(stream_uri)
        playlist = m3u8.loads(r.text)
        init_section = self.__prefix_url + playlist.data['segments'][0]['init_section']['uri']
        r_init = requests.get(init_section)

        m4s_pathname = f'video_{tweet_id}.m4s'
        mp4_pathname = f'video_{tweet_id}.mp4'

        if isfile(mp4_pathname):
            remove(mp4_pathname)

        with open(m4s_pathname, "wb") as f:
            f.write(r_init.content)
            for segment in playlist.data['segments']:
                segment_uri = self.__prefix_url + segment['uri']
                r = requests.get(segment_uri)
                f.write(r.content)
        try:
            subprocess.run(['ffmpeg', '-i', m4s_pathname, mp4_pathname], capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            # print(e)
            remove(m4s_pathname)
            raise RuntimeError(f'{tweet_id}: video download failed: could not convert to mp4')

        remove(m4s_pathname)

        # print(f'video downloaded successfully as {mp4_pathname}')
        return(mp4_pathname)

    def __download_gif(self, variants, tweet_id, save_gif_as_mp4=True):
        """
        Download and save gif attachment from tweet

        Args:
            variants (list): list of variant stream playlists available for download
            tweet_id (str): Tweet to download gif from
        """
        media_url = variants[0]['url']

        mp4_pathname = f'video_{tweet_id}.mp4'
        # temp_gif = f'temp_{tweet_id}.gif'
        # final_gif = f'animated_{tweet_id}.gif'

        with open(mp4_pathname, "wb") as f:
            r = requests.get(media_url)
            f.write(r.content)

        if save_gif_as_mp4:
            return (mp4_pathname)

    def __convert_time(self, input_time):
        """
        Converts time from api to format printed on video

        Args:
            input_time (str): Time string to be converted
        """
        # Convert input_time string to datetime object
        time_obj = datetime.strptime(input_time[:19], '%Y-%m-%dT%H:%M:%S')

        # Format datetime object in desired format
        output_time = time_obj.strftime('%I:%M %p · %b %d, %Y')

        return output_time

    def clean_temp_files(self, screenshot_path, resized_screenshot, footer, video_file):
        """
        Delete temporary files

        Args:
            screenshot_path (str): Path to screenshot file
            resized_screenshot (str): Path to screenshot file resized to fit video
            footer (str): Path to footer image file
            video_file (str): Path to downloaded video file
        """
        if screenshot_path and isfile(screenshot_path):
            remove(screenshot_path)
        if resized_screenshot and isfile(resized_screenshot):
            remove(resized_screenshot)
        if footer and isfile(footer):
            remove(footer)
        if video_file and isfile(video_file):
            remove(video_file)

    def generate_clip(self, tweet_id, night_mode=0, round_margin=15, squared=False):
        """
        Makes nice memeable clips from tweets with video or gif attachments

        Args:
            tweet_id (int): id of tweet with video/gif attachment
            night_mode (int): the dark mode to make
        """
        tweet = self.__get_tweet(tweet_id)
        # if tweet is None:
        #     return

        # Paths to temp files
        screenshot_path = None
        resized_screenshot = None
        footer = None
        # video_file = None

        username = tweet.get('username')
        tweet_time = tweet.get('time')
        video_file = tweet.get('video_path')

        try:
            screenshoter = self.__screenshoter

            # Get Screenshot
            screenshot_path = f'screenshot_temp_{tweet_id}.png'
            tweet_url = f'https://twitter.com/{username}/status/{tweet_id}'
            screenshot_path =  run(screenshoter.screenshot(tweet_url, screenshot_path, mode=0, night_mode=night_mode))

            # Load screenshot
            screenshot = Image.open(screenshot_path)
            screenshot = ImageUtils.crop_screenshot(screenshot, night_mode)

            # Load video
            video = VideoFileClip(f'{video_file}')
            video_width, video_height = video.size

            if squared:
                screenshot = ImageUtils.resize_image(screenshot, width=720)
                video = ImageUtils.video_for_square(video, screenshot, round_margin)
            else:
                if video_width / video_height < 4 / 5 :
                    fit_margin = int(((video_height * (4 / 5)) - video_width) / 2)
                    video = video.margin(left=fit_margin, right=fit_margin)

            # Add rounded corner
            rounded_video = ImageUtils.rounded_corner_effect(video, round_margin, night_mode)
            video_width, video_height = rounded_video.size

            screenshot = ImageUtils.resize_image(screenshot, width=video_width)
            resized_screenshot = f'resized_screenshot_{username}_{tweet_id}.png'
            screenshot.save(resized_screenshot)
            screenshot_clip = ImageClip(resized_screenshot).set_duration(video.duration)

            # Footer
            time_stamp = self.__convert_time(tweet_time)
            footer = ImageUtils.make_footer(time_stamp, video_width, night_mode)
            footer_clip = ImageClip(footer).set_duration(video.duration)

            if squared:
                screenshot_clip = screenshot_clip.resize(width=720)
                rounded_video = rounded_video.resize(width=720)
                footer_clip = footer_clip.resize(width=720)

            final_clip = clips_array([[screenshot_clip], [rounded_video], [footer_clip]])

            if squared:
                final_clip = final_clip.resize((720, 720))
            else:
                final_clip = ImageUtils.size_video(final_clip, 720)

            save_path = f'{username}_{tweet_id}.mp4'
            final_clip.write_videofile(save_path, fps=30, audio_codec='aac')

        except:
            self.clean_temp_files(screenshot_path, resized_screenshot, footer, video_file)
            raise RuntimeError(f'{tweet_id}: Clip generation failed')


        self.clean_temp_files(screenshot_path, resized_screenshot, footer, video_file)

    def close_screenshoter(self):
        self.__screenshoter.close_driver()


if __name__ == '__main__':
    clipper = TweetClipper('keys.json')

    try:
        while True:
            tweet_id = input('Enter tweet id: ')
            night_mode = input('Enter night mode: ')
            squared = input('To be squared or not [y/n]: ')
            if squared.lower() == 'y':
                squared = True
            elif squared.lower() == 'n':
                squared = False
            clipper.generate_clip(tweet_id, night_mode=night_mode, squared=squared)
            to_exit = input('Should exit [y/n]: ')

            if to_exit == 'y':
                break
    except Exception as e:
        clipper.close_screenshoter()
        raise e

    clipper.close_screenshoter()
