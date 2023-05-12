import concurrent.futures
import json
import requests
import tweepy
import m3u8
import subprocess
from asyncio import run
from datetime import datetime
from os import remove
from os.path import isfile
from engine.MyTweetCapture import MyTweetCapture
from engine.ImageUtils import ImageUtils
# from MyTweetCapture import MyTweetCapture
# from ImageUtils import ImageUtils
from PIL import Image
from moviepy.editor import ImageClip, clips_array, VideoFileClip
from multiprocessing import current_process


class TweetClipper:

    __size = 'medium'
    __prefix_url = 'https://video.twimg.com'
    __round_margin = 15

    def __init__(self, keys_file):
        """
        Initialize a TweetClipper instance

        Args:
            keys_file (str): path to json file containing twitter api v2 keys with read and write access enabled
        """
        with open(keys_file) as k:
            auth_keys = json.loads(k.read())

        self.__api_client = tweepy.Client(bearer_token=auth_keys['bearer_token'], access_token=auth_keys['access_token'], access_token_secret=auth_keys['access_token_secret'], consumer_key=auth_keys['consumer_key'], consumer_secret=auth_keys['consumer_secret'], return_type=dict, wait_on_rate_limit=True)

        if current_process().name == 'MainProcess':
            self.__screenshoter = MyTweetCapture()
            run(self.__screenshoter.start_driver())
            self.__screenshoter.hide_all_media()

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
            bandwidth = playlist.get('stream_info').get('average_bandwidth')
            if bandwidth is None:
                bandwidth = playlist.get('stream_info').get('bandwidth')
            bandwidths.append(bandwidth)

        bandwidths = sorted(bandwidths)

        if size == 'small':
            bandwidth_size = bandwidths[0]
        elif size == 'large':
            bandwidth_size = bandwidths[-1]
        else:
            bandwidth_size = bandwidths[len(bandwidths) // 2]

        if playlist.get('stream_info').get('average_bandwidth') is not None:
            for playlist in playlists:
                if playlist['stream_info']['average_bandwidth'] == bandwidth_size:
                    stream_uri = playlist['uri']
                    break
        else:
            for playlist in playlists:
                if playlist['stream_info']['bandwidth'] == bandwidth_size:
                    stream_uri = playlist['uri']
                    break


        stream_uri = self.__prefix_url + stream_uri

        r = requests.get(stream_uri)
        playlist = m3u8.loads(r.text)

        init_section = playlist.data['segments'][0].get('init_section')

        if init_section:
            init_section_uri = self.__prefix_url + playlist.data['segments'][0].get('init_section').get('uri')
            r_init = requests.get(init_section_uri)

        first_chunk_uri = self.__prefix_url + playlist.data['segments'][0]['uri']
        ext = first_chunk_uri.split('.')[-1]
        stream_pathname = f'video_{tweet_id}. + ext'
        mp4_pathname = f'video_{tweet_id}.mp4'

        if isfile(mp4_pathname):
            remove(mp4_pathname)

        with open(stream_pathname, "wb") as f:
            if init_section:
                f.write(r_init.content)
            for segment in playlist.data['segments']:
                segment_uri = self.__prefix_url + segment['uri']
                r = requests.get(segment_uri)
                f.write(r.content)
        try:
            subprocess.run(['ffmpeg', '-i', stream_pathname, mp4_pathname], capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            # print(e)
            remove(stream_pathname)
            raise RuntimeError(f'{tweet_id}: video download failed: could not convert to mp4')

        remove(stream_pathname)

        # print(f'video downloaded successfully as {mp4_pathname}')
        return mp4_pathname

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
            return mp4_pathname

    def __clean_temp_files(self, screenshot_path, resized_screenshot, footer, video_file):
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

    def _get_screenshot(self, tweet_id, username, night_mode):
        """
        Takes screenshot of a tweet and returns a PIL object of the opened screenshot

        Args:
            tweet_id: tweet id of tweet to be screenshoted
        """
        screenshoter = self.__screenshoter

        # Get Screenshot
        screenshot_path = f'screenshot_temp_{tweet_id}.png'
        tweet_url = f'https://twitter.com/{username}/status/{tweet_id}'

        try:
            screenshot_path =  run(screenshoter.screenshot(tweet_url, screenshot_path, mode=0, night_mode=night_mode))
        except:
            raise RuntimeError(f'{tweet_id}: screenshot failed')

        # Load screenshot
        screenshot = Image.open(screenshot_path)
        screenshot = ImageUtils.crop_screenshot(screenshot, night_mode)

        return {'screenshot': screenshot, 'screenshot_path': screenshot_path}

    def _get_tweet(self, tweet_id, size=None):
            """
            Get tweet details, download and save media (video/gif) from tweet

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
                # raise RuntimeError(f'{tweet_id}: Tweet does not have video or gif attachment')
                return None

            if media_type == 'video':
                video_path = self.__download_video(variants, tweet_id, size)
            if media_type == 'animated_gif':
                video_path = self.__download_gif(variants, tweet_id)

            return {'tweet_id': tweet_id, 'username': username, 'time': tweet_time, 'video_path' : video_path}

    def batch_screenshot(self, job_list):
        """
        Generates multiple clips from a list of tweets

        Args:
            job_list (list): List of dictionaries containing the tweet id, username, night mode and square preference for the clip to be made
        """

        screenshots = {}

        for job in job_list:
            tweet_id = job.get('tweet_to_capture')
            username = job.get('username')
            night_mode = job.get('night_mode')

            try:
                screenshot = self._get_screenshot(tweet_id, username, night_mode)
            except:
                raise RuntimeError(f'{tweet_id}: screenshot failed')

            screenshots[tweet_id] = screenshot
            # print('tweet_id type:', type(tweet_id))

        return screenshots


    def _clippify(self, tweet, screenshot, screenshot_path, night_mode=0, squared=False):
        """
        Generate final clips
        """

        round_margin = self.__round_margin

        # # Load screenshot
        # screenshot = Image.open(screenshot_path)
        # screenshot = ImageUtils.crop_screenshot(screenshot, night_mode)

        # Paths to temp files
        resized_screenshot = None
        footer = None
        # video_file = None

        tweet_id = tweet.get('tweet_id')
        username = tweet.get('username')
        tweet_time = tweet.get('time')
        video_filename = tweet.get('video_path')

        # Load video
        video = VideoFileClip(f'{video_filename}')
        video_width, video_height = video.size

        try:
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

        except Exception as e:
            # self.__clean_temp_files(screenshot_path, resized_screenshot, footer, video_filename)
            raise e
            # raise RuntimeError(f'{tweet_id}: Clip generation failed')

        self.__clean_temp_files(screenshot_path, resized_screenshot, footer, video_filename)
        return(save_path)

    def generate_clip(self, tweet_id, night_mode=0, squared=False):
        """
        Makes nice memeable clips from tweets with video or gif attachments

        Args:
            tweet_id (int): id of tweet with video/gif attachment
            night_mode (int): the dark mode to make
        """
        tweet = self._get_tweet(tweet_id)
        if tweet is None:
            raise RuntimeError(f'{tweet_id}: Tweet does not have video or gif attachment')
            # return


        username = tweet.get('username')
        # tweet_time = tweet.get('time')
        # video_file = tweet.get('video_path')

        try:
            screenshot_obj = self._get_screenshot(tweet_id, username, night_mode)
        except:
            raise RuntimeError(f'{tweet_id}: screenshot failed')

        screenshot = screenshot_obj.get('screenshot')
        screenshot_path = screenshot_obj.get('screenshot_path')

        try:
            res = self._clippify(tweet, screenshot, screenshot_path, night_mode=night_mode, squared=squared)
        except Exception as e:
            raise e
            # raise RuntimeError(f'{tweet_id}: Could not generate tweet clip')

        return res

    def bot_generate_clips(self, args):
        """
        Generate clip method for bot use, with preprocessed screenshots
        """
        tweet_id = args.get('tweet_to_capture')
        # tweet_to_reply = args.get('tweet_to_reply')
        screenshot = args.get('screenshot')
        screenshot_path = args.get('screenshot_path')
        night_mode = args.get('night_mode')
        squared = args.get('squared')

        tweet_details = self._get_tweet(tweet_id)
        if tweet_details is None:
            remove(screenshot_path)
            return None

        try:
            save_path = self._clippify(tweet_details, screenshot, screenshot_path, night_mode=night_mode, squared=squared)
        except:
            raise RuntimeError(f'{tweet_id}: Could not generate tweet clip')

        # return {'tweet_to_reply': tweet_to_reply, 'save_path': save_path}
        return save_path

    def multiprocess_clip_generation(self, mentions):
        """
        Generate final clips with multiprocessing
        """
        clips = []
        with concurrent.futures.ProcessPoolExecutor() as executor:
            for result in executor.map(self.batch_generate_clips, mentions):
                clips.append(result)

        return clips


    def close_screenshoter(self):
        self.__screenshoter.close_driver()


if __name__ == '__main__':
    clipper = TweetClipper('keys.json')

    try:
        while True:
            tweet_id = input('Enter first tweet id: ')
            night_mode = int(input('Enter night mode: '))
            squared = input('To be squared or not [y/n]: ')
            if squared.lower() == 'y':
                squared = True
            elif squared.lower() == 'n':
                squared = False

            clipper.generate_clip(tweet_id, night_mode=night_mode, squared=squared)
            to_exit  = input('Are you done or not [y/n]: ')
            if to_exit == 'y':
                break
    except Exception as e:
        clipper.close_screenshoter()
        raise e

    # clipper.close_screenshoter()

    # jobs = [{'tweet_id': 1645636242963419142, 'username': 'InsaneRealitys', 'night_mode': 1},
    #         {'tweet_id': 1645793901952008192, 'username': 'Carnage4Life', 'night_mode': 2},
    #         {'tweet_id': 1645771943797219329, 'username': 'EndWokeness', 'night_mode': 0}
    #         ]
    # clipper.multiple_clips(jobs)

    clipper.close_screenshoter()
