This is repository for os-version-checker.

Os-Version-Checker will check and compare self
from upstream against debian.

Using templates/datatables 

    pip install -r requirements.txt

    python VersionsStatus.py
    
    Usage: VersionStatus.py [OPTIONS]

    Options:
      -r, --releases <columns>       Separate status page per one release, which
                                     chosen.  [default: stein,train,ussuri]
    
      -ff, --file-format [txt|html]  Output file format.  [default: html]
      -fn, --file-name TEXT          Output file name
      -s, --separated                If chosen, then output is in separated files.
      -h, --help                     Show this message and exit.


