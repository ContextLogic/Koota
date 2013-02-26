import tinycss
import codecs

class TingCSSParser(object):
    def __init__(self):
        self._parser = tinycss.make_parser()

    def parse_css_file(self, file_path):
        css_text = ""
        with codecs.open(file_path, 'r', "utf-8") as f:
            css_text = f.read()
        return self.parse_

    def parse_css_str(self, css_str):
        return self._parser.parse_stylesheet(css_str, "utf-8")
