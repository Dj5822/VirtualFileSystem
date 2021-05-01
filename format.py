import disktools
import time

from stat import S_IFDIR, S_IFLNK, S_IFREG

"""
File metadata:
MODE # 2 bytes
UID # 2 bytes
GID # 2 bytes

CTIME # 4 bytes
MTIME # 4 bytes
ATIME # 4 bytes

NLINKS # 1 byte
SIZE # 2 bytes, size of file in bytes
LOCATION # up to you how you do this

NAME # can be here or elsewhere, 16 byte length allowed
= 37 bytes minimum.
One block = 64 bytes.
"""
def write_metadata(block_num, metadata):
    block = disktools.read_block(block_num)
    block[0:2]=disktools.int_to_bytes(metadata['st_mode'], 2)
    block[2:4]=disktools.int_to_bytes(metadata['st_mode'], 2)
    block[4:6]=disktools.int_to_bytes(metadata['st_mode'], 2)
    
    block[6:10]=disktools.int_to_bytes(int(metadata['st_ctime']), 4)
    block[10:14]=disktools.int_to_bytes(int(metadata['st_mtime']), 4)
    block[14:18]=disktools.int_to_bytes(int(metadata['st_atime']), 4)

    block[18:19]=disktools.int_to_bytes(metadata['st_nlink'], 1)
    block[19:21]=disktools.int_to_bytes(metadata['size'], 1)
    block[21:22]=disktools.int_to_bytes(metadata['location'], 1)

    block[22:38]=bytes(metadata['name'], 'utf-8')

    disktools.write_block(block_num, block)

    # for testing
    print(disktools.read_block(block_num))
    print(len(disktools.read_block(block_num)))


# True means the block is empty and False means the block is being used.
# First 5 blocks will store metadata.
empty_file_block_list = [False, True, True, True, True]
# The next 11 blocks will contain file data.
empty_data_block_list = [True, True, True, True, True, True, True, True, True, True, True]

now = time.time()

metadata = dict(
    st_mode=(S_IFDIR | 0o755),
    st_uid=1000,
    st_gid=1000,
    st_ctime=now,
    st_mtime=now,
    st_atime=now,
    st_nlink=2,
    size=0,
    location=0,
    name='/')

# clear disk
disktools.low_level_format()
# write metadata
write_metadata(0, metadata)

