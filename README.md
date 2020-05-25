This is repository for os-version-checker.

Os-Version-Checker will check and compare self
from upstream against debian.

Using templates/datatables 

    pip install -r requirements.txt

    python3 VersionsStatus.py
    
    Usage: VersionStatus.py [OPTIONS]
    
    Options:
      -r, --releases <releases>  Separate status page per one release, which
                                 chosen.  [default: stein,train,ussuri]
    
      -t, --type [txt|html]      Output file format.  [default: html]
      -f, --file TEXT            Output file name
      -s, --separated            If chosen, then output is in separated files.
      -h, --help                 Show this message and exit.



