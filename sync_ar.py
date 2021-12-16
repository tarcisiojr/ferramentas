from __future__ import print_function

import socket
socket.setdefaulttimeout(4000)

from business.accounts_receivable import sync_acount_receivables


def main():
    sync_acount_receivables()


if __name__ == '__main__':
    main()

