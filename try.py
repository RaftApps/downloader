from pytube import YouTube

def download_youtube_4k(url, output_path='.'):
    """
    Downloads the highest resolution (including 4K) available for a YouTube video.

    Args:
        url (str): The URL of the YouTube video.
        output_path (str): The directory to save the downloaded video.
    """
    try:
        yt = YouTube(url)
        print(yt)
        # Filter for streams with a resolution of 2160p (4K) or the highest available
        # and ensure it's a progressive stream (audio and video combined)
        stream = yt.streams.filter(res='2160p', progressive=True).first()
        print(stream)
        if not stream:
            # If 4K progressive stream is not found, get the highest resolution progressive stream
            stream = yt.streams.filter(progressive=True).get_highest_resolution()
            print(stream)
        if stream:
            print(f"Downloading: {yt.title} in {stream.resolution}...")
            stream.download(output_path)
            print(f"Download complete! Saved to: {output_path}")
        else:
            print("No suitable stream found for download.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    video_url = input("Enter the YouTube video URL: ")
    download_youtube_4k(video_url)