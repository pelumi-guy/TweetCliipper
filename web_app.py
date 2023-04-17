from flask import Flask
from flask import request
from engine.TweetClipper import TweetClipper

app = Flask(__name__)

# clipper = TweetClipper('engine/keys.json')

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.post("/test/json")
def test_json():
    req = request.get_json()
    return f"""
        <h1>PARSED JSON PAYLOAD:<h1>
        <p>tweet_id: {req.get('tweet_id')}<p>
        <p>username: {req.get('username')}<p>
        """

@app.post("/clip")
def make_clip():
    clipper = TweetClipper('engine/keys.json')
    req  = request.get_json()
    tweet_id = req.get('tweet_id')
    night_mode = req.get('night_mode')
    squared = req.get('squared')
    if squared == 1:
        squared = True
    elif squared == 0:
        squared = False
    else:
        squared = False
    res = clipper.generate_clip(tweet_id, night_mode=night_mode, squared=squared)
    clipper.close_screenshoter()
    return {"clip saved at": res}

@app.post("/screenshot")
def make_screenshot():
    clipper = TweetClipper('engine/keys.json')
    req  = request.get_json()
    tweet_id = req.get('tweet_id')
    username = req.get('username')
    night_mode = req.get('night_mode')
    r = clipper._get_screenshot(tweet_id, username, night_mode)
    res = {"screenshot saved at": r.get('screenshot_path')}
    clipper.close_screenshoter()
    return res


if __name__ == '__main__':
    app.run(debug=True)