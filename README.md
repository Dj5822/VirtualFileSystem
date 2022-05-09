# VirtualFileSystem
A virtual file system created using Python.

Only works on Linux. Please use WSL on Windows.
Assumes that you have Python3 installed.
You can also use older versions of Python, but the command would use
python instead of python3.

Execute the following commands: 
```
mkdir mount
python3 disktools.py
python3 format.py
python3 small.py mount
```

You can now do the following operations: touch, echo, cat, ls, rm, mkdir, rmdir

Execute the following to check the disk:
`od --address-radix=x -t x1 -a my-disk`



