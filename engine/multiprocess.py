import concurrent.futures

def generate_clips(mentions, clipper):
    clips = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        for result in executor.map(clipper.bot_generate_clips, mentions):
            clips.append(result)

    return clips