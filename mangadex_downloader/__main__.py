import sys
import os
import argparse
import logging
import signal
from getpass import getpass
from .network import Net
from .main import download, login, logout
from .utils import get_language, validate_url as __validate
from .utils import _keyboard_interrupt_handler, Language, valid_cover_types, default_cover_type
from .errors import ChapterNotFound, HTTPException, InvalidURL, LoginFailed
from .update import check_version, update_app
from . import __description__

def setup_logging(name_module, verbose=False):
    log = logging.getLogger(name_module)
    handler = logging.StreamHandler()
    fmt = logging.Formatter('[%(levelname)s] %(message)s')
    handler.setFormatter(fmt)
    log.addHandler(handler)
    if verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    return log

def _validate(url):
    try:
        _id = __validate(url)
    except InvalidURL as e:
        raise argparse.ArgumentTypeError(str(e))
    return _id

def validate_url(url):
    if os.path.exists(url):
        with open(url, 'r') as opener:
            return [_validate(i) for i in opener.read().splitlines()]
    else:
        return _validate(url)

def validate_language(lang):
    try:
        return get_language(lang)
    except Exception as e:
        raise argparse.ArgumentTypeError(str(e))

def list_languages():
    text = ""
    for lang in Language:
        text += "%s = %s; " % (lang.name, lang.value)
    return text

def _main(argv):
    lowered_argv = [i.lower() for i in argv]
    if '--update' in lowered_argv:
        setup_logging('mangadex_downloader')
        update_app()
        sys.exit(0)

    parser = argparse.ArgumentParser(description=__description__)
    parser.add_argument('URL', type=validate_url, help='MangaDex URL or a file containing MangaDex URLs')
    parser.add_argument('--folder', metavar='FOLDER', help='Store manga in given folder')
    parser.add_argument('--replace', help='Replace manga if exist', action='store_true')
    parser.add_argument('--proxy', metavar='SOCKS / HTTP Proxy', help='Set http/socks proxy')
    parser.add_argument('--proxy-env', action='store_true', help='use http/socks proxy from environments')
    parser.add_argument('--verbose', help='Enable verbose output', action='store_true')
    parser.add_argument(
        '--start-chapter',
        type=float,
        help='Start download chapter from given chapter number',
        metavar='CHAPTER'
    )
    parser.add_argument(
        '--end-chapter',
        type=float,
        help='Stop download chapter from given chapter number',
        metavar='CHAPTER'
    )
    parser.add_argument('--use-compressed-image', help='Use low size images manga (compressed quality)', action='store_true')
    parser.add_argument('--no-oneshot-chapter', help='If exist, don\'t download oneshot chapter', action='store_true')
    parser.add_argument('--login', help='Login to MangaDex', action='store_true')
    parser.add_argument(
        '--login-username',
        help='Login to MangaDex with username (you will be prompted to input password if --login-password are not present)',
        metavar='USERNAME'
    )
    parser.add_argument(
        '--login-password',
        help='Login to MangaDex with password (you will be prompted to input username if --login-username are not present)',
        metavar='PASSWORD'
    )
    parser.add_argument(
        '--language',
        metavar='LANGUAGE',
        help='Download manga in given language, to see all languages, use --list-languages option',
        type=validate_language,
        default=Language.English
    )
    parser.add_argument(
        '--list-languages',
        action='version',
        help='List all available languages',
        version=list_languages()
    )
    parser.add_argument(
        '--cover',
        choices=valid_cover_types,
        help='Choose quality cover, default is \"original\"',
        default=default_cover_type
    )
    args = parser.parse_args(argv)

    log = setup_logging('mangadex_downloader', args.verbose)

    if args.login:
        if not args.login_username:
            username = input("MangaDex username => ")
        else:
            username = args.login_username
        if not args.login_password:
            password = getpass("MangaDex password => ")
        else:
            password = args.login_password

        # Logging in
        login_success = False
        for _ in range(5):
            attempt = _ + 1
            try:
                login(password, username)
            except LoginFailed as e:
                sys.exit(1)
            except ValueError as e:
                log.error(e)
                sys.exit(1)
            except HTTPException as e:
                log.info(
                    'Login failed because of MangaDex server error, status code: %s. ' \
                    'Trying again... (attempt: %s)',
                    e.response.status_code,
                    attempt
                )
            else:
                login_success = True
                break

        if not login_success:
            log.error("5 attempts login failed, exiting...")
            sys.exit(1)
            

    # Give warning if --proxy and --proxy-env is present
    if args.proxy and args.proxy_env:
        log.warning('--proxy and --proxy-env options are present, --proxy option will be ignored')

    if args.proxy_env:
        log.debug('Using proxy from environments')
    Net.trust_env = args.proxy_env
    if args.proxy:
        log.debug('Setting up proxy from --proxy option')
        Net.set_proxy(args.proxy)

    def dl(url):
        try:
            download(
                url,
                args.folder,
                args.replace,
                args.use_compressed_image,
                args.start_chapter,
                args.end_chapter,
                args.no_oneshot_chapter,
                args.language,
                args.cover
            )
        except ChapterNotFound as e:
            log.error(str(e))

    if isinstance(args.URL, list):
        for url in args.URL:
            dl(url)
    else:
        dl(args.URL)

    if args.login:
        logout_success = False
        for _ in range(5):
            attempt = _ + 1
            try:
                logout()
            except HTTPException as e:
                log.info(
                    'Logout failed because of MangaDex server error, status code: %s. ' \
                    'Trying again... (attempt: %s)',
                    e.response.status_code,
                    attempt
                )
            else:
                logout_success = True
                break
        
        if not logout_success:
            log.error("5 attempts logout failed, ignoring...")

    log.debug('Checking update...')
    latest_version = check_version()
    if latest_version:
        log.info("There is new version mangadex-downloader ! (%s), you should update it with \"%s\" option" % (
            latest_version,
            '--update'
        ))
    elif latest_version == False:
        sys.exit(1)
    else:
        log.debug("No update found")

    log.debug("Cleaning up...")
    log.debug('Closing network object')
    Net.close()

def main(argv=None):
    # Register KeyboardInterrupt handler
    signal.signal(signal.SIGINT, _keyboard_interrupt_handler)

    if argv is None:
        _main(sys.argv[1:])
    else:
        _main(argv)

if __name__ == "__main__":
    main()

