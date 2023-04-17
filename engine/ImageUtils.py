from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, CompositeVideoClip
from os import remove
import uuid


class ImageUtils:

    color_red = (255, 0, 0, 255)
    transparent = (0, 0, 0, 0)
    white = (255, 255, 255)
    black = (0, 0, 0)
    dim = (21, 32, 43)

    def select_color(self, night_mode):
        if night_mode == 0:
            return self.white
        elif night_mode == 1:
            return self.dim
        elif night_mode == 2:
            return self.black
        else:
            return self.white

    def color_replace(self, image, color_to_replace, replacement_color):
        """
        Replace a specified colour in an image
        """
        pixdata = image.load()

        width, height = image.size
        for y in range(height):
            for x in range(width):
                if pixdata[x, y] == color_to_replace:
                    pixdata[x, y] = replacement_color

        return image

    @classmethod
    def crop_screenshot(cls, image, night_mode):
        """
        Crop screenshot to remove excels pixels beneath
        """
        base_color = cls.select_color(cls, night_mode)
        pixdata = image.load()
        width, height = image.size
        backgroundColor = pixdata[width - 1, height - 1]

        if backgroundColor != (*base_color, 255):
            return image

        for y in reversed(range(height)):
            found = False
            for x in reversed(range(width)):
                if pixdata[x, y] != backgroundColor:
                    found = True
                    break
            if found:
                break

        y += 11
        # print(f'height: {y}')
        return image.crop((0, 0, width, y))

    # --- Make picture frame with inner rounded corner ---
    def make_frame(self, width, height, margin, radius, night_mode):
        """
        Make picture frame with inner rounded corner to fit video in
        """
        base_color = self.select_color(self, night_mode)
        # self.test_method('boy', 'girl')
        # Create base_image with white background
        base_image = Image.new('RGBA', (width, height), color=base_color)

        overlay_width = width - (margin * 2)
        overlay_height = height - (margin * 2)

        # Create the overlay image
        overlay_image = Image.new('RGBA', (overlay_width, overlay_height), color=base_color)

        # Draw a rectangle with rounded corners on the image
        draw = ImageDraw.Draw(overlay_image)
        # x1, y1 = overlay_image.size

        if night_mode == 2:
            draw.rounded_rectangle((0, 0, overlay_width, overlay_height), fill=self.color_red, radius=radius, width=2, outline=self.dim)
        else:
            draw.rounded_rectangle((0, 0, overlay_width, overlay_height), fill=self.color_red, radius=radius)

        # Calculate the position to paste the overlay image at the center of the base image
        x_pos = int((width - overlay_width) / 2)
        y_pos = int((height - overlay_height) / 2)

        # Paste the overlay image onto the base image at the calculated position
        base_image.paste(overlay_image, (x_pos, y_pos))

        final_image = self.color_replace(self, base_image, self.color_red, self.transparent)

        # Save the result to a new image file
        identifier = uuid.uuid4()
        save_path = f'rounded_frame_{identifier}.png'
        final_image.save(save_path)
        return save_path

    # --- Make rounded corner video ---
    @classmethod
    def rounded_corner_effect(cls, video, mar, night_mode):
        border_radius = 16
        video_width, video_height = video.size
        new_dimensions = (video_width - (mar * 2), video_height - (mar * 2))
        base_color = cls.select_color(cls, night_mode)

        # use margin method
        video = video.resize(new_dimensions)
        margin_clip = video.margin(mar=mar, color=base_color)
        x, y = margin_clip.size
        frame = cls.make_frame(cls, x, y, mar, border_radius, night_mode)
        frame_clip = ImageClip(frame).set_duration(margin_clip.duration)
        final_clip = CompositeVideoClip([margin_clip, frame_clip])
        remove(frame)

        # # Write the final clip to a file
        # final_clip.write_videofile("video_with_margin.mp4")

        return final_clip

    # --- Resize images and keep aspect ratio ---
    @staticmethod
    def resize_image(image: Image.Image, width=None, height=None) -> Image.Image:
        if height is None and width is not None:
            height = image.height * width // image.width
        elif width is None and height is not None:
            width = image.width * height // image.height
        elif height is None and width is None:
            raise RuntimeError("At lease one of width and height must be present")
        return image.resize((width, height))

    def test_method(self, arg1, arg2):
        print(f'args: {arg1} {arg2}')

    @classmethod
    def make_footer(cls, text, width, night_mode):
        """
        Make Footer with watermark for video
        """
        height = int(width * (1 / 18))
        text_size = int(height * (1 / 2))
        base_color = cls.select_color(cls, night_mode)
        textColor = cls.black if night_mode == 0 else cls.white
        watermark_width = int(width * (6 / 25))
        watermark_template = 'engine/resources/light_mode.png' if night_mode == 0 else 'engine/resources/dark_mode.png'

        footer = Image.new('RGB', (width, height), color=base_color)
        canvas = ImageDraw.Draw(footer)
        chirpFont = ImageFont.truetype("engine/resources/Chirp.ttf", text_size, encoding="utf-8")
        canvas.text((int(0.03 * width), int(0.5 * height)), text, font=chirpFont, fill=textColor, anchor='lm')

        watermark = Image.open(watermark_template)
        watermark = ImageUtils.resize_image(watermark, width=watermark_width)

        # Calculate the position to place the watermark at the bottom-right corner of the image
        watermark_x = footer.width - watermark.width
        watermark_y = footer.height - watermark.height

        # Paste the watermark onto the footer at the calculated position
        footer.paste(watermark, (watermark_x, watermark_y), watermark)

        identifier = uuid.uuid4()
        save_path = f'footer_{identifier}.png'
        footer.save(save_path)

        return save_path

    @staticmethod
    def video_for_square(video, screenshot, round_margin):
        video_width, video_height = video.size
        squared_video_height = int((18 / 19) * (720 - screenshot.height))

        if video_height / video_width < squared_video_height / 720:
            video = video.resize(width=720)
            video_width, video_height = video.size
            fit_margin = int((squared_video_height - video_height - (round_margin * 2)) / 2)
            video = video.margin(top=fit_margin, bottom=fit_margin)
            video = video.resize(height=squared_video_height)
        else:
            video = video.resize(height=squared_video_height)
            video_width, video_height = video.size
            fit_margin = int((720 - video_width - (round_margin * 2)) / 2)
            video = video.margin(left=fit_margin, right=fit_margin)
            video = video.resize(width=720)

        return video

    @staticmethod
    def size_video(video, size):
        """
        Resize video by making the smaller side equal to specified size while maintaining aspect ratio

        Args:
            video (moviepy: Video clip to resize
            size (int): new size of video
        """
        video_width, video_height = video.size
        if video_width < video_height:
            height = video_height * size // video_width
            if height % 2 != 0:
                height -= 1
            return video.resize((size, height))
        else:
            width = video_width * size // video_height
            if width % 2 != 0:
                width -= 1
            return video.resize((width, size))












if __name__ == '__main__':
    testImageUtils = ImageUtils()
    testImageUtils.make_frame(0, 0, 0, 0)