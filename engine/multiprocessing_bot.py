import concurrent.futures
import tweepy
import json
from TweetClipper import engine
import multiprocess
from multiprocessing import current_process, freeze_support



# clipper2 = TweetClipper('keys.json')

# def clipper_wrapper (tweet_id, kwargs):
#      clipper = TweetClipper('keys.json')
#      clipper.generate_clip(tweet_id, **kwargs)

# while True:
#     tweet_id1 = input('Enter first tweet id: ')
#     tweet_id2 = input('Enter second tweet id: ')
#     night_mode = int(input('Enter night mode: '))
#     squared = input('To be squared or not [y/n]: ')
#     if squared.lower() == 'y':
#         squared = True
#     elif squared.lower() == 'n':
#         squared = False

#     kwargs = {'night_mode': night_mode, 'squared': squared}

#     with ProcessPoolExecutor(max_workers=3) as executor:
#             executor.submit(clipper_wrapper, tweet_id1, **kwargs)
#             executor.submit(clipper_wrapper, tweet_id2, **kwargs)

#     to_exit  = input('Are you done or not [y/n]: ')

#     if to_exit == 'y':
#         break



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
        # to_be_clipped['screenshot'] = screenshots.get(tweet_id).get('screenshot')
        to_be_clipped['screenshot_path'] = screenshots.get(tweet_id).get('screenshot_path')

        mentions_to_clip.append(to_be_clipped)

    return mentions_to_clip

def generate_clips(mentions):
    clips = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        for result in executor.map(clipper.bot_generate_clips, mentions):
            clips.append(result)

    return clips

global clipper
clipper = engine('keys.json')

with open('keys.json') as k:
    auth_keys = json.loads(k.read())

bot_client = tweepy.Client(bearer_token=auth_keys['bearer_token'], access_token=auth_keys['access_token'], access_token_secret=auth_keys['access_token_secret'], consumer_key=auth_keys['consumer_key'], consumer_secret=auth_keys['consumer_secret'], return_type=dict, wait_on_rate_limit=True)

expansions = 'attachments.media_keys,author_id,referenced_tweets.id.author_id'
mentions = bot_client.get_users_mentions(1632150906597695488, expansions=expansions, max_results=5, media_fields="variants", since_id=1645325964421783552)

mentions = parse_mentions(mentions)

if current_process().name == 'MainProcess':
    mentions = screenshot_handler(mentions)

print('mentions:', mentions)

if __name__ == '__main__':
    # freeze_support()
    clips = []
    for mention in mentions:
        try:
            # clips = clipper.multiprocess_clip_generation(mentions)
            clip = clipper.batch_generate_clips(mention)
        except Exception as e:
            if current_process().name == 'MainProcess':
                clipper.close_screenshoter()
            raise e
        clips.append(clip)

    print('clips:', clips)

    if current_process().name == 'MainProcess':
        clipper.close_screenshoter()