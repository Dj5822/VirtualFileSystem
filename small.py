#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

import logging
import disktools

from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from time import time

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

from format import empty_file_block_list
from format import empty_data_block_list
import os

if not hasattr(__builtins__, 'bytes'):
    bytes = str

class Small(LoggingMixIn, Operations):
    'Example memory filesystem. Supports only one level of files.'

    """
    The disk will contain the file attributes and the file data.
    We can store the file attributes in the first 4 blocks.
    We can store the file data in the other 12 blocks.
    """
    def __init__(self):
        # System wide open file table.
        self.files = {}

        self.fd = 0
        # Find out which blocks are empty and which are full.
        for i in range(len(empty_file_block_list)):
            if disktools.bytes_to_int(disktools.read_block(i)[18:19]) != 0:
                empty_file_block_list[i] = False
                block = disktools.read_block(i)
                name = block[22:38].decode()
                if i == 0:
                    name = '/'
                # load metadata to memory.
                self.files[name] = dict(
                    st_mode=disktools.bytes_to_int(block[0:2]),
                    st_uid=disktools.bytes_to_int(block[2:4]),
                    st_gid=disktools.bytes_to_int(block[4:6]),
                    st_ctime=disktools.bytes_to_int(block[6:10]),
                    st_mtime=disktools.bytes_to_int(block[10:14]),
                    st_atime=disktools.bytes_to_int(block[14:18]),
                    st_nlink=disktools.bytes_to_int(block[18:19]),
                    st_size=disktools.bytes_to_int(block[19:21]),
                    st_location=disktools.bytes_to_int(block[21:22]),
                    block_num=i)

        self.create("test1", 777)

    def chmod(self, path, mode):
        self.files[path]['st_mode'] &= 0o770000
        self.files[path]['st_mode'] |= mode

        block_num = self.files[path]['st_location']
        block = disktools.read_block(block_num)
        block[0:2] = disktools.int_to_bytes(self.files[path]['st_mode'], 2)
        disktools.write_block(block_num, block)   

        return 0

    def chown(self, path, uid, gid):
        self.files[path]['st_uid'] = uid
        self.files[path]['st_gid'] = gid

        block_num = self.files[path]['st_location']
        block = disktools.read_block(block_num)
        block[2:4] = disktools.int_to_bytes(self.files[path]['st_uid'], 2)
        block[2:4] = disktools.int_to_bytes(self.files[path]['st_mode'], 2)
        disktools.write_block(block_num, block)  
        

    # adds a new file by adding file attributes to the files dictionary.
    # whenever a file is created, fd will be incremented and returned (fd is basically the id for the file).
    # mode is the permissions that you want the file to have.
    def create(self, path, mode):

        file_name = os.path.basename(path)
        block_num = -1
        data_location = -1

        # find an empty block for metadata
        for i in range(len(empty_file_block_list)):
            if empty_file_block_list[i] == True:
                block_num = i

        # find an empty block for data
        for i in range(len(empty_data_block_list)):
            if empty_data_block_list[i] == True:
                data_location = i
                empty_file_block_list[block_num] = False
                empty_data_block_list[i] == False

        self.files[file_name] = dict(
            st_mode=(S_IFREG | mode),
            st_uid=1000,
            st_gid=1000,
            st_ctime=int(time()),
            st_mtime=int(time()),
            st_atime=int(time()),
            st_nlink=1,
            st_size=0,
            st_location=data_location,
            block_num=block_num)

        if block_num != -1 and data_location != -1:
            block = disktools.read_block(block_num)
            block[0:2]=disktools.int_to_bytes(self.files[file_name]['st_mode'], 2)
            block[2:4]=disktools.int_to_bytes(self.files[file_name]['st_uid'], 2)
            block[4:6]=disktools.int_to_bytes(self.files[file_name]['st_gid'], 2)
            
            block[6:10]=disktools.int_to_bytes(self.files[file_name]['st_ctime'], 4)
            block[10:14]=disktools.int_to_bytes(self.files[file_name]['st_mtime'], 4)
            block[14:18]=disktools.int_to_bytes(self.files[file_name]['st_atime'], 4)

            block[18:19]=disktools.int_to_bytes(self.files[file_name]['st_nlink'], 1)
            block[19:21]=disktools.int_to_bytes(self.files[file_name]['st_size'], 1)
            block[21:22]=disktools.int_to_bytes(self.files[file_name]['st_location'], 1)

            block[22:38]=file_name.encode('ascii')

            disktools.write_block(block_num, block)

        # for testing
        print(disktools.read_block(block_num))
        print(len(disktools.read_block(block_num)))

        self.fd += 1
        return self.fd

    # if the file exists, then it will return the attributes of the file.
    def getattr(self, path, fh=None):
        
        if path not in self.files:
            raise FuseOSError(ENOENT)

        return self.files[path]

    def getxattr(self, path, name, position=0):
        attrs = self.files[path].get('attrs', {})

        try:
            return attrs[name]
        except KeyError:
            return ''       # Should return ENOATTR

    def listxattr(self, path):
        attrs = self.files[path].get('attrs', {})
        return attrs.keys()
    # similar to create, however the number of st_nlink is 2 instead of 1.
    def mkdir(self, path, mode):
        self.files[path] = dict(
            st_mode=(S_IFDIR | mode),
            st_nlink=2,
            st_size=0,
            st_ctime=time(),
            st_mtime=time(),
            st_atime=time())

        self.files['/']['st_nlink'] += 1

    # passes the file path of the file that you want open and increment the file descriptor.
    def open(self, path, flags):
        self.fd += 1
        return self.fd

    # starts reading from the offset until offset + size.
    def read(self, path, size, offset, fh):
        return self.data[path][offset:offset + size]

    def readdir(self, path, fh):
        return ['.', '..'] + [x[1:] for x in self.files if x != '/']

    def readlink(self, path):
        return self.data[path]

    def removexattr(self, path, name):
        attrs = self.files[path].get('attrs', {})

        try:
            del attrs[name]
        except KeyError:
            pass        # Should return ENOATTR

    def rename(self, old, new):
        self.data[new] = self.data.pop(old)
        self.files[new] = self.files.pop(old)

    def rmdir(self, path):
        # with multiple level support, need to raise ENOTEMPTY if contains any files
        self.files.pop(path)
        self.files['/']['st_nlink'] -= 1

    def setxattr(self, path, name, value, options, position=0):
        # Ignore options
        attrs = self.files[path].setdefault('attrs', {})
        attrs[name] = value

    def statfs(self, path):
        return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)

    def symlink(self, target, source):
        self.files[target] = dict(
            st_mode=(S_IFLNK | 0o777),
            st_nlink=1,
            st_size=len(source))

        self.data[target] = source

    def truncate(self, path, length, fh=None):
        # make sure extending the file fills in zero bytes
        self.data[path] = self.data[path][:length].ljust(
            length, '\x00'.encode('ascii'))
        self.files[path]['st_size'] = length

    def unlink(self, path):
        self.data.pop(path)
        self.files.pop(path)

    def utimens(self, path, times=None):
        now = time()
        atime, mtime = times if times else (now, now)
        self.files[path]['st_atime'] = atime
        self.files[path]['st_mtime'] = mtime

    # receives the file path, data, and offset.
    # modifies the file data such that it removes everything after the offset
    # and replaces it with the new data.
    # file size will also be updated.
    def write(self, path, data, offset, fh):
        self.data[path] = (
            # make sure the data gets inserted at the right offset
            self.data[path][:offset].ljust(offset, '\x00'.encode('ascii'))
            + data
            # and only overwrites the bytes that data is replacing
            + self.data[path][offset + len(data):])
        self.files[path]['st_size'] = len(self.data[path])
        return len(data)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mount')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    fuse = FUSE(Small(), args.mount, foreground=True)
