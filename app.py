import os, sys, json, re, logging
from logging import handlers
from configparser import ConfigParser
from datetime import datetime
from requests import Session
from bs4 import BeautifulSoup

class App:

    def __init__(self, WD):
        self.WD = WD                        # Working Directory
        self._logger = App.initLogger(WD)   # Logger initialization
        self._conf = None                   # Variable of configuration
        self._data = None                   # Data of crawling
        self._update = None                 # Result of comparing data

    # =============================================================================
    # -- static methods
    # =============================================================================

    @staticmethod
    def initLogger(WD):
        log_dir = os.path.join(WD, 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        logger = logging.getLogger('coronachk')
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter('[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s - %(message)s')
        f_handler = handlers.RotatingFileHandler(os.path.join(log_dir,'coronachk.log'), 'a', 10 * 1024 * 1024, 5)
        f_handler.setFormatter(fmt)
        logger.addHandler(f_handler)
        return logger

    @staticmethod
    def at():
        return datetime.now().strftime('%Y/%m/%d %H:%M:%S')

    @staticmethod
    def asInt(str_):
        return re.findall("\d+", str_)[0]

    @staticmethod
    def parse(soup):
        items = soup.find('div', class_='co_cur').find_all('li')
        return {'at':App.at(),
                'confirm':App.asInt(items[0].text),
                'discharge':App.asInt(items[1].text),
                'check':App.asInt(items[2].text)}

    @staticmethod
    def msg(recent, diffs, url):
        msg = """<br>
        코로나바이러스감염증-19 현황<br>
        --------------------<br>
        확진환자수 증가 : {diff_c}<br>
        격리해제 환자수 증가 : {diff_d}<br>
        --------------------<br>
        확진환자수 : {confirm}<br>
        확진환자 격리해제수 : {discharge}<br>
        검사진행수 : {check}<br><br>
        아프지 말자..<br><br>
        Check at : {at}<br>
        더보기 : {url}   
        """
        return msg.format(diff_c=diffs[0], diff_d=diffs[1], confirm=recent['confirm'], discharge=recent['discharge'], check=recent['check'], at=recent['at'], url=url)

    # =============================================================================
    # -- private instance methods
    # =============================================================================

    #   - loading configuration file
    def _load_conf(self, file_name='app.conf'):
        file = os.path.join(self.WD, file_name)
        parser = ConfigParser()
        parser.read(file, encoding='utf-8-sig')
        self._conf = parser

    #   - Loading data
    def _load(self, file_name='data.json'):
        file = os.path.join(self.WD, file_name)

        # - 1st loading
        if not os.path.isfile(file):
            with open(file, 'w', encoding='utf8') as f:
                json.dump({"title":"코로나바이러스감염증-19 현황","data":[]}, f, ensure_ascii=False)

        with open(file, 'r', encoding='utf8')as f:
            tmp = json.load(f)
            tmp['data'] = tmp['data'][:10]
            self._data = tmp

    #   - saving data
    def _save(self, file_name='data.json'):
        file = os.path.join(self.WD, file_name)

        with open(file, 'w', encoding='utf8') as f:
            json.dump(self._data, f, ensure_ascii=False)


    #   - crawling
    def _crawl(self):
        if not self._data:
            self._load()
        if not self._conf:
            self._load_conf()

        url = self._conf['default']['url']
        session = Session().get(url)

        if session.status_code != 200:
            raise Exception("Wrong page.. Check your url")

        html = session.text
        session.close()
        soup = BeautifulSoup(html, 'lxml')
        data = App.parse(soup)

        self._data['data'].insert(0, data)
        self._save()

    #   - Check the change
    def _isChanged(self):
        try:
            prev = self._data['data'][1]
            next = self._data['data'][0]

            diff_confirm = int(next['confirm']) - int(prev['confirm'])
            diff_discharge = int(next['discharge']) - int(prev['discharge'])

            self._update = [diff_confirm, diff_discharge]

            return diff_confirm != 0 or diff_discharge != 0
        except Exception as e:
            self._logger.warning(e)
            return False


    #   - Request for webhooks
    def _hooks(self):
        session = Session()
        target = self._conf['ifttt']['url']
        value1 = App.msg(self._data['data'][0], self._update, self._conf['default']['url'])
        session.post(target, data={"value1":value1})
        session.close()


    # =============================================================================
    # -- run
    # =============================================================================
    def run(self):
        try:
            self._logger.info('Start check process')

            self._crawl()

            if self._isChanged():
                # 상태변화 O
                self._logger.info('Change in number of patients, send notification')
                self._hooks()
            else:
                # 상태변화 X
                self._logger.info('No change in number of patients')

        except Exception as e:
            _, _, tb = sys.exc_info()
            self._logger.warning('line : {}\n{}'.format(tb.tb_lineno, e))
        finally:
            self._logger.info('End Check process')


if __name__ == '__main__':
    WD = os.path.dirname(os.path.abspath(__file__))

    app = App(WD)
    app.run()
