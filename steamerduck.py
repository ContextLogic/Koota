import re
import sys
import codecs
import tinycss
import Image
import os
import hashlib

class FreeSpaceNode(object):
    PADDING = 5 # pad each sub image by 5px
    def __init__(self, x_pos, y_pos, size_x, size_y):
        self.children   = []
        self.size_x     = size_x
        self.size_y     = size_y
        self.x_pos      = x_pos
        self.y_pos      = y_pos
        self.file_name  = None
        self.image      = None

    @property
    def is_free(self):
        return not self.image

    def init_children(self, image_w, image_h, free_w, free_h):
        self.children = [
            FreeSpaceNode(
                self.x_pos + image_w + self.PADDING,
                self.y_pos,
                free_w - image_w - self.PADDING,
                image_h,
            ),
            FreeSpaceNode(
                self.x_pos,
                self.y_pos + image_h + self.PADDING,
                free_w,
                free_h - image_h - self.PADDING,
            ),
        ]

    def _add_image(self, image, file_name, size_x, size_y):
        self.image      = image
        self.file_name  = file_name
        self.size_x     = size_x + (self.PADDING * 2)
        self.size_y     = size_y + (self.PADDING * 2)
        self.x_pos      = self.x_pos + self.PADDING
        self.y_pos      = self.y_pos + self.PADDING
    
    def image_fits(self, image):
        size_x, size_y = image.size
        return size_x + (self.PADDING * 2) < self.size_x \
            and size_y + (self.PADDING * 2) <  self.size_y

    def insert_image(self, image, file_name):
        assert self.is_free, "I am not free space!"
        size_x, size_y = image.size
        assert self.image_fits(image), "Not enough space for this image"

        if size_x < self.size_x and size_y < self.size_y:
            self.init_children(
                image_w = size_x,
                image_h = size_y,
                free_w  = self.size_x,
                free_h  = self.size_y,
            )
            self._add_image(
                image     = image,
                file_name = file_name,
                size_x    = size_x,
                size_y    = size_y,
            )
    
    def create_image(self, new_image):
        for child in self.children:
            child.create_image(new_image)

        if self.image:
            new_image.paste(self.image, (self.x_pos, self.y_pos))

    def _to_string(self, depth):
        ret_str = "\t"*depth + "%s : (%s, %s, %s, %s)" % (
            self.file_name, self.x_pos, self.y_pos, self.size_x, self.size_y)
        for child in self.children:
            ret_str += "\n%s" % child._to_string(depth+1)
        return ret_str

    def to_string(self):
        return self._to_string(0)

    @classmethod
    def walk(cls, node):
        yield node
        for child in node.children:
            for n in cls.walk(child):
                yield n

class Sprite(object):
    def __init__(self, size_x, size_y):
        self.size_x     = size_x
        self.size_y     = size_y
        self.space_tree = FreeSpaceNode(0, 0, size_x, size_y)

    def insert_image(self, image, file_name):
        for node in FreeSpaceNode.walk(self.space_tree):
            if node.is_free and node.image_fits(image):
                node.insert_image(image, file_name)
                return True
        return False

    def image_iter(self):
        for node in FreeSpaceNode.walk(self.space_tree):
            if not node.is_free:
                yield (
                    node.image,
                    node.file_name,
                    node.x_pos,
                    node.y_pos,
                )
    
    def get_size(self):
        size_x = size_y = 0
        for node in FreeSpaceNode.walk(self.space_tree):
            if not node.is_free:
                far_x = node.size_x + node.x_pos
                far_y = node.size_y + node.y_pos
                if size_x < far_x:
                    size_x = far_x
                if size_y < far_y:
                    size_y = far_y
        return size_x, size_y

    def create_image(self):
        size_x, size_y = self.get_size()
        new_image = Image.new("RGBA", (size_x, size_y))
        self.space_tree.create_image(new_image)
        md5_value = hashlib.md5(new_image.tostring()).hexdigest()
        self.file_name = "w_%s.png" % md5_value
        new_image.save(self.file_name, "PNG")

    def to_string(self):
        return self.space_tree.to_string()

class SteamerDuck(object):
    def __init__(self, image_directory, image_regex = None):
        self.image_directory = image_directory
        self.image_regex = image_regex
        if not self.image_regex:
            self.image_regex = '(?<=url\(")[^}]*(?="\))'
    
    def parse_css_file(self, file_path):
        with codecs.open(file_path, 'r', "utf-8") as f:
            css_text = f.read()
        return self.parse_css_str(css_text)

    def parse_css_str(self, css_str):
        parser = tinycss.make_parser()
        return parser.parse_stylesheet(css_str, "utf-8")

    def stylesheet_to_css(self, stylesheet):
        css = ""
        for ruleset in stylesheet.rules:
            decl_css = ""
            for decl in ruleset.declarations:
                decl_css += "%s:%s;" % (decl.name, decl.value.as_css());
            css += "%s{%s}" % (ruleset.selector.as_css(), decl_css)
        return css

    def url_from_ruleset(self, ruleset):
        url = width = height = None
        background_position  = None
        for declaration in ruleset.declarations:
            decl_css    = declaration.value.as_css()
            if 'background' in declaration.name or \
                    'background-image' in declaration.name:
                url         = re.findall(
                    self.image_regex,
                    decl_css,
                )
                if 'top'    in decl_css or \
                   'bottom' in decl_css or \
                   'left'   in decl_css or \
                   'right'  in decl_css or \
                   'center' in decl_css or \
                   '%'      in decl_css or \
                   'px'     in decl_css or \
                   'em'     in decl_css:
                    background_position = decl_css
            if 'width' in declaration.name:
                width = decl_css
            if 'height' in declaration.name:
                height = decl_css
            if 'background-position' in declaration.name:
                background_position = decl_css
        if not height and not width and not background_position:
            return url
        return None

    def spritable_ruleset_iter(self, stylesheet):
        for pos, rule_set in enumerate(stylesheet.rules):
            url = self.url_from_ruleset(rule_set)
            if not url:
                continue
            url_chunks = url[0].split("/")
            image = url_chunks[-1]
            image_file_name = image.split("?")[0]
            yield pos, image_file_name

    def squawk(self, file_path):
        stylesheet = self.parse_css_file(file_path)
       
        rs_position_to_file_name = {}
        for position, file_name in self.spritable_ruleset_iter(stylesheet):
            rs_position_to_file_name[position] = file_name

        images_by_name = {}
        for file_name in rs_position_to_file_name.itervalues():
            if file_name in images_by_name:
                continue
            file_path = os.path.join(self.image_directory, file_name)
            if os.path.exists(file_path):
                images_by_name[file_name] = Image.open(file_path)
            else:
                print "%s not found in %s" % (file_name, self.image_directory)
        
        images = [(n,i) for n,i in images_by_name.iteritems()]
        images = sorted(images, key = lambda i: i[1].size[0] * i[1].size[1])
        images.reverse()

        sprites = [Sprite(400,300)]
        for file_name, image in images:
            size_x, size_y = image.size
            if size_x > 300 or size_y > 200:
                continue

            was_inserted = False
            for cur_sprite in sprites:
                if cur_sprite.insert_image(image, file_name):
                    was_inserted = True
                    break

            if not was_inserted:
                new_sprite = Sprite(400, 300)
                new_sprite.insert_image(image, file_name)
                sprites.append(new_sprite)

        file_name_to_css_info = {}
        for sprite in sprites:
            sprite.create_image()
            for orig_image, file_name, x_pos, y_pos in sprite.image_iter():
                assert file_name not in file_name_to_css_info, \
                    "%s in two sprites!" % file_name
                sizex, sizey = image.size
                file_name_to_css_info[file_name] = {
                    'width'         : sizex,
                    'height'        : sizey,
                    'x_pos'         : x_pos,
                    'y_pos'         : y_pos,
                    'original_name' : file_name,
                    'sprite_name'   : sprite.file_name,
                }

        '''
        for pos, ruleset in enumerate(stylesheet.rules):
            if pos not in rs_position_to_file_name:
                continue
            file_name = rs_position_to_file_name[pos]
            css_info = file_name_to_css_info[file_name]
            background_decls = [d for d in ruleset.declarations \
                if 'background' in d.name]
            for decl in background_decls:
                for token in decl.value:
                    if file_name in token.value:
                        token._as_css = token._as_css.replace(
                            file_name,
                            css_info['sprite_name'],
                        )
            ruleset.declarations.append(tinycss.css21.Declaration(
                name  = 'background-position',
                value = [tinycss.token_data.Token(
                    None,
                    '%dpx %dpx'%(css_info['x_pos'], css_info['y_pos']),
                    None, None, None, None)]
            ))
        '''

        with open("result.css", "w") as out_file:
            out_file.write(self.stylesheet_to_css(stylesheet));

def main():
    steamer_duck = SteamerDuck('img/')
    steamer_duck.squawk(sys.argv[1])

if __name__ == "__main__":
    main()
