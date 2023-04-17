from TweetClipper import engine

clipper1 = engine('keys.json')
clipper2 = engine('keys.json')

print('clipper1:', clipper1)
print('clipper2:', clipper2)

clipper1.close_screenshoter()
clipper2.close_screenshoter()