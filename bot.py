import concurrent.futures
import tweepy
import json
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
import cloudinary
from engine.TweetClipper import TweetClipper
from multiprocessing import current_process, freeze_support


def parse_mentions(mentions):
    mentioning_tweets = []
    for mention in mentions.get('data'):
        tweet = {}
        tweet['tweet_to_reply'] = mention.get('id')
        ref_tweets = mention.get('referenced_tweets')
        for ref_tweet in ref_tweets:
            if ref_tweet['type'] == 'replied_to':
                tweet['tweet_to_capture'] = ref_tweet.get('id')

        author_id = tweet['author_id'] = mention.get('author_id')

        r = bot_client.get_user(id=author_id)
        tweet['username'] = r.get('data').get('username')

        text = mention.get('text')

        if 'dark' in text.lower():
            tweet['night_mode'] = 1
        elif 'black' in text.lower():
            tweet['night_mode'] = 2
        else:
            tweet['night_mode'] = 0

        if 'squared' in text.lower():
            tweet['squared'] = True
        else:
            tweet['squared'] = False

        mentioning_tweets.append(tweet)

    return mentioning_tweets

def screenshot_handler(mentions):
    screenshots = clipper.batch_screenshot(mentions)

    mentions_to_clip = []
    for mention in mentions:
        to_be_clipped = {**mention}
        tweet_id = mention.get('tweet_to_capture')
        # tweet_details = clipper._get_tweet(tweet_id)
        # if tweet_details is None:
        #     continue

        # to_be_clipped['tweet'] = tweet_details
        to_be_clipped['screenshot'] = screenshots.get(tweet_id).get('screenshot')
        to_be_clipped['screenshot_path'] = screenshots.get(tweet_id).get('screenshot_path')

        mentions_to_clip.append(to_be_clipped)

    return mentions_to_clip

def generate_clips_with_multiprocessing(mentions):
    clips = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        for result in executor.map(clipper.bot_generate_clips, mentions):
            clips.append(result)

    return clips

def generate_and_upload(mentions):
    for mention in mentions:
        try:
            clip = clipper.bot_generate_clips(mention)
        except Exception as e:
            raise e

        # tweet_to_reply = mention.get('tweet_to_reply')
        # if clip is not None:
        #     upload_data = upload(clip, resource_type="video", folder="TweetClipper")
        #     print('upload successful:', upload_data)

def retrieve_last_seen_id(file_name):
    f_read = open(file_name, 'r')
    last_seen_id = int(f_read.read().strip())
    f_read.close()
    return last_seen_id

def store_last_seen_id(last_seen_id, file_name):
    f_write = open(file_name, 'w')
    f_write.write(str(last_seen_id))
    f_write.close()
    return

if __name__ == '__main__':
    FILE_NAME = 'bot_last_seen.txt'

    clipper = TweetClipper('engine/keys.json')

    with open('engine/keys.json') as k:
        auth_keys = json.loads(k.read())

    bot_client = tweepy.Client(bearer_token=auth_keys['bearer_token'], access_token=auth_keys['access_token'], access_token_secret=auth_keys['access_token_secret'], consumer_key=auth_keys['consumer_key'], consumer_secret=auth_keys['consumer_secret'], return_type=dict, wait_on_rate_limit=True)

    cloudinary.config(
    cloud_name = auth_keys['cloudinary_cloud_name'],
    api_key = auth_keys['cloudinary_api_key'],
    api_secret = auth_keys['cloudinary_api_secret'],
    secure = True
    )

    last_seen_id = retrieve_last_seen_id(FILE_NAME)

    expansions = 'attachments.media_keys,author_id,referenced_tweets.id.author_id'
    mentions = bot_client.get_users_mentions(1632150906597695488, expansions=expansions, max_results=5, media_fields="variants", since_id=last_seen_id)

    mentions = parse_mentions(mentions)

    mentions = screenshot_handler(mentions)

    print('mentions:', mentions)

    try:
        generate_and_upload(mentions)
    except Exception as e:
        clipper.close_screenshoter()
        raise e

    # print('clips:', clips)

    last_seen_id = mentions[-1].get('tweet_to_capture')

    if last_seen_id:
        store_last_seen_id(last_seen_id, FILE_NAME)

    clipper.close_screenshoter()