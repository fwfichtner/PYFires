import bz2
from datetime import datetime
import s3fs
from pathlib import Path


def get_him(date_str: str = "2024/12/09", ts: str = "0120"):
    """
    Get HIM data from S3 and unpack.
    """
    bucket = "noaa-himawari9"
    prefix = f"AHI-L1b-FLDK/{date_str}/{ts}"
    fs = s3fs.S3FileSystem(anon=True)
    files = fs.ls(f"{bucket}/{prefix}")
    dest = Path(__file__).parent.parent.joinpath("testfiles/him")
    dest.mkdir(parents=True, exist_ok=True)
    for file in files:
        with fs.open(file, 'rb') as f:
            compressed_data = f.read()
        
        decompressed_data = bz2.decompress(compressed_data)

        output_file = dest.joinpath(ts).joinpath(Path(file.removesuffix(".bz2")).name)
        with open(output_file, 'wb') as f:
            f.write(decompressed_data)
                

if __name__ == "__main__":
    # get today
    ds = datetime.now().strftime("%Y/%m/%d")
    get_him(date_str=ds)
