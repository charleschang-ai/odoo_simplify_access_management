# -*- coding: utf-8 -*-
"""移除邮件 HTML 中的 "Powered by Odoo" 品牌区块(公共实现)。

核心邮件模板(portal 邀请、auth_signup 重置密码、digest 等十几个模块)
的 body_html 里都内嵌同一结构的区块::

    <!-- POWERED BY -->
    <tr><td align="center" ...>
        <table ... background-color: #F1F1F1 ...>
          <tr><td>Powered by <a href="https://www.odoo.com?...">Odoo</a></td></tr>
        </table>
    </td></tr>

只删文字会留下一条空的灰色横带;用正则删整块又会在嵌套表格下误吞
正文。这里以 odoo.com 链接为锚点,用 lxml 逐层向上收拢到
"整个子树只含品牌短语"的最外层节点(即包住灰色表格的外层 <tr>),
整块删除。按文本内容而非固定文案匹配,因此对翻译后的正文同样生效
(如 zh_CN 的"由<a>Odoo</a>驱动")。lxml 解析失败时退回保守正则,
只删文字与链接,不动结构。
"""
import logging
import re

from lxml import etree, html as lxml_html

_logger = logging.getLogger(__name__)

# 品牌短语容器的可见文本上限:任何语言的 "Powered by Odoo" 短语都很短,
# 超过该长度说明该容器是正文内容,放弃整块删除。
_MAX_BLOCK_TEXT = 40
# 除品牌链接外,短语容器里其余文字的上限(各语言的 "Powered by" 短语)
_MAX_PHRASE_TEXT = 20

# 品牌链接的锚文本必须是 "Odoo" 或 "Odoo XXX"(如 Odoo CRM);
# 用户在正文里贴的裸网址链接(锚文本是 URL)不会命中,不受影响。
_BRAND_TEXT_RE = re.compile(r'^odoo(?:\s+[\w.-]+)?$', re.IGNORECASE)

# 保守回退(lxml 解析失败时用):仅移除品牌文字与链接,不动 HTML 结构。
# href 可能是静态 href,也可能是 qweb 动态属性 t-attf-href / t-att-href
# (如 auth_signup 的 "Settings: New Portal User Invite" 模板)。
_FALLBACK_RE = re.compile(
    r'(?:Powered\s+by\s*|由\s*)?'
    r'<a\b[^>]*(?:t-attf?-)?href="[^"]*odoo\.com[^"]*"[^>]*>\s*Odoo\s*</a>'
    r'(?:\s*驱动)?\.?',
    re.IGNORECASE)

_POWERED_COMMENT_RE = re.compile(r'powered\s*by', re.IGNORECASE)


def _norm_text(node):
    return ' '.join(node.text_content().split())


def _link_href(link):
    """链接目标:兼容静态 href 与 qweb 动态属性 t-attf-href / t-att-href。"""
    for attr in ('href', 't-attf-href', 't-att-href'):
        value = link.get(attr)
        if value:
            return value.lower()
    return ''


# 指向 odoo.com 首页(可带 utm 参数)的链接:锚文本可能已被品牌词替换改成
# 自有品牌(如 "MyBrand"),仍应视为品牌链接
_ROOT_ODOO_HREF_RE = re.compile(r'^(?:https?:)?//(?:www\.)?odoo\.com/?(?:[?#].*)?$', re.IGNORECASE)
_MAX_ROOT_LINK_TEXT = 30


def _is_brand_link(link):
    href = _link_href(link)
    if 'odoo.com' not in href:
        return False
    text = _norm_text(link)
    return bool(_BRAND_TEXT_RE.match(text)) or (
        bool(_ROOT_ODOO_HREF_RE.match(href)) and 0 < len(text) <= _MAX_ROOT_LINK_TEXT)


def _unwrap(link):
    """去掉链接、保留其文字(句中的品牌链接,如 auth_signup 邀请邮件里
    "<公司> uses <a href=odoo.com>Odoo</a> to run its business")。"""
    parent = link.getparent()
    text = link.text_content() + (link.tail or '')
    prev = link.getprevious()
    if prev is not None:
        prev.tail = (prev.tail or '') + text
    else:
        parent.text = (parent.text or '') + text
    parent.remove(link)


def _subtree_clean(container, link):
    """容器子树里除品牌链接外,不得有其他链接/图片/qweb 动态节点。"""
    for el in container.iter():
        if el is link or not isinstance(el.tag, str):
            continue  # 跳过链接本身与注释/PI 节点
        if el.tag in ('a', 'img'):
            return False  # 还有其他链接/图片,不能整块删
        if any(k.startswith('t-') for k in el.attrib):
            return False  # 含动态 qweb 节点,防误删业务内容
    return True


def _block_root(link, stop_node):
    """从品牌链接向上找可整块删除的最外层祖先。

    第一步:链接的直接父级必须是"短语容器" — 可见文本只是一个很短的
    品牌短语(如 "Powered by Odoo" / "由Odoo驱动"),且除链接外没有其他
    链接/图片/qweb 动态节点;否则说明链接嵌在正文里,返回链接本身。

    第二步:严格结构收拢 — 仅当父节点不引入任何新文本、且当前节点是
    父节点唯一的元素子节点时才继续向上(td → tr → 灰色 table → 外层
    td → 外层 tr),任何兄弟内容都会让收拢停在正确的层级。"""
    container = link.getparent()
    if container is None or container is stop_node:
        return link
    text = _norm_text(container)
    # 去掉链接文字后剩下的只能是品牌短语本身("Powered by"、"由…驱动"、
    # "Propulsé par" 等),否则是一句正常的话(如 "ACME uses Odoo to run its
    # business."),整块删除会把正文一起删掉。
    other_text = text.replace(_norm_text(link), '', 1).strip()
    if (len(text) > _MAX_BLOCK_TEXT or len(other_text) > _MAX_PHRASE_TEXT
            or not _subtree_clean(container, link)):
        return link
    best = container
    while True:
        parent = best.getparent()
        if parent is None or parent is stop_node or parent.tag in ('html', 'body'):
            break
        if _norm_text(parent) != text:
            break  # 父级引入了新的可见文本(兄弟节点有内容)
        if [c for c in parent if isinstance(c.tag, str)] != [best]:
            break  # 父级还有其他元素子节点
        best = parent
    return best


# 行内品牌链接前的固定短语(如 digest 页脚 "Sent by Odoo – Unsubscribe",
# 中文 "发送者 Odoo – 退订"):只认这几个短语,避免误删正文里的普通文字。
_LEAD_PHRASE_RE = re.compile(r'(?:(?:sent|powered)\s+by|发送者|由)\s*$', re.IGNORECASE)
# 链接之后的残留:中文 "驱动" 后缀与 "–" / "|" 等分隔符
_TRAIL_RE = re.compile(r'^\s*(?:驱动)?\.?\s*(?:[–—\-|·•]\s*)?')


def _drop_inline_brand(link):
    """链接嵌在一行里、与其他链接同处一个容器时(无法整块删除):
    仅当它前面紧挨着 "Sent by / Powered by / 发送者 / 由" 短语时,
    把短语、链接及紧随的分隔符一起删掉。返回是否删除。"""
    prev = link.getprevious()
    parent = link.getparent()
    before = (prev.tail if prev is not None else parent.text) or ''
    match = _LEAD_PHRASE_RE.search(before)
    if not match:
        return False
    before = before[:match.start()]
    if prev is not None:
        prev.tail = before
    else:
        parent.text = before
    link.tail = _TRAIL_RE.sub(' ' if before.strip() else '', link.tail or '', count=1)
    _drop(link)
    return True


# Odoo 官方 App 推广(如 digest 邮件的 "Run your business from anywhere with
# Odoo Mobile" 横幅):以 App 商店链接与 odoo.com / odoocdn 图片为锚点
_PROMO_HREF_RE = re.compile(
    r'com\.odoo\.mobile|apple\.com/[^"\s]*/app/odoo', re.IGNORECASE)
_PROMO_SRC_RE = re.compile(r'(?:^|//)(?:[\w-]+\.)*(?:odoo\.com|odoocdn\.com)/', re.IGNORECASE)
_MAX_PROMO_TEXT = 200


def _promo_anchors(root):
    for el in root.iter('a', 'img'):
        if el.tag == 'a' and _PROMO_HREF_RE.search(el.get('href') or ''):
            yield el
        elif el.tag == 'img' and _PROMO_SRC_RE.search(el.get('src') or ''):
            yield el


# re.ASCII:中文字符在 Unicode 模式下也算单词字符,"您的Odoo帐户" 这种
# 中英文紧挨的写法(zh_CN 译文里很常见)会因没有单词边界而匹配不到
_ODOO_WORD_RE = re.compile(r'\bodoo\b', re.IGNORECASE | re.ASCII)


def _is_odoo_href(href):
    href = (href or '').strip().lower()
    return (not href or href.startswith('#') or 'odoo.com' in href
            or 'odoocdn.com' in href or bool(_PROMO_HREF_RE.search(href)))


def _has_foreign_link(node):
    """子树里是否有指向别处(非 Odoo 推广)的链接,如退订/切换周报:
    含这类链接的节点属于业务内容,不能整块删除。"""
    return any(not _is_odoo_href(a.get('href')) for a in node.iter('a'))


def _is_promo_subtree(node):
    """兄弟节点本身也是推广内容:含推广锚点,或文案里提到 Odoo。"""
    return (any(True for _ in _promo_anchors(node))
            or bool(_ODOO_WORD_RE.search(_norm_text(node))))


def _promo_block(anchor, stop_node):
    """从推广锚点向上收拢到"整块只有这段推广"的最外层节点:
    父级可见文本不超过上限、不含指向别处的链接、其余有内容的兄弟
    也都是推广内容时才继续向上。"""
    best = anchor
    while True:
        parent = best.getparent()
        if parent is None or parent is stop_node or parent.tag in ('html', 'body'):
            break
        if len(_norm_text(parent)) > _MAX_PROMO_TEXT or _has_foreign_link(parent):
            break
        own_text = ' '.join(((parent.text or '') + ' '.join(
            (c.tail or '') for c in parent if isinstance(c.tag, str))).split())
        if own_text and not _ODOO_WORD_RE.search(own_text):
            break
        if any(not _is_promo_subtree(c) for c in parent
               if isinstance(c.tag, str) and c is not best and _norm_text(c)):
            break
        best = parent
    return best


# Odoo 自带的 logo 图片(如 account 的 "New eInvoices Notification" /
# "Journal Notification" 邮件页眉右侧的白色 odoo 字标
# /web/static/img/logo_inverse_white_206px.png)。公司 logo 走 /logo.png 或
# /web/binary/company_logo,不会命中。
_ODOO_LOGO_SRC_RE = re.compile(
    r'/web/static/img/(?:logo|odoo_logo|odoo_icon)[\w.-]*\.(?:png|svg|jpe?g|webp)\b',
    re.IGNORECASE)


def _img_src(img):
    """图片地址:兼容静态 src 与 qweb 动态属性 t-attf-src / t-att-src。"""
    for attr in ('src', 't-attf-src', 't-att-src'):
        value = img.get(attr)
        if value:
            return value
    return ''


def _is_odoo_logo(img):
    return bool(_ODOO_LOGO_SRC_RE.search(_img_src(img)))


def _attached(node, root):
    while node is not None:
        if node is root:
            return True
        node = node.getparent()
    return False


def _drop(node):
    """删除节点,但把尾随文本(tail)合并回文档,避免相邻文字丢失。"""
    parent = node.getparent()
    if parent is None:
        return
    tail = node.tail or ''
    if tail:
        prev = node.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or '') + tail
        else:
            parent.text = (parent.text or '') + tail
    parent.remove(node)


# 独立的 "Odoo" 品牌词(不匹配 odoo.com / odoo.sh 等域名片段)
_BRAND_WORD_RE = re.compile(r'\bodoo\b(?!\.(?:com|sh))', re.IGNORECASE | re.ASCII)

# 品牌词替换跳过的元素:样式/脚本里的 odoo 多为类名或 URL
_SKIP_TAGS = {'style', 'script'}


def replace_odoo_text(text, brand):
    """纯文本(如邮件主题)中的独立 "Odoo" 品牌词替换为自有品牌名。"""
    if not text or not brand:
        return text
    return _BRAND_WORD_RE.sub(brand, text)


def replace_odoo_word(html_str, brand):
    """HTML 文本节点中的独立 "Odoo" 品牌词替换为自有品牌名。

    只处理元素的 text/tail 文本,不碰任何属性(href/src 里的域名安全),
    跳过 <style>/<script>。未命中或未配置品牌名时原样返回入参。"""
    if not html_str or not brand:
        return html_str
    source = str(html_str)
    if not _BRAND_WORD_RE.search(source):
        return html_str
    wrapper = html_str.__class__
    try:
        root = lxml_html.fragment_fromstring(source, create_parent='div')
    except (etree.ParserError, etree.XMLSyntaxError, ValueError):
        return html_str
    changed = False
    for el in root.iter():
        # tail 是元素之后的文本,属于父级内容,任何节点都要处理
        if el.tail and _BRAND_WORD_RE.search(el.tail):
            el.tail = _BRAND_WORD_RE.sub(brand, el.tail)
            changed = True
        if not isinstance(el.tag, str) or el.tag in _SKIP_TAGS:
            continue
        if el.text and _BRAND_WORD_RE.search(el.text):
            el.text = _BRAND_WORD_RE.sub(brand, el.text)
            changed = True
    if not changed:
        return html_str
    out = lxml_html.tostring(root, encoding='unicode', method='html')
    start = out.index('>') + 1
    end = out.rindex('<')
    return wrapper(out[start:end])


def _parse_fragment(html_str):
    try:
        return lxml_html.fragment_fromstring(str(html_str), create_parent='div')
    except (etree.ParserError, etree.XMLSyntaxError, ValueError):
        return None


def _serialize_fragment(root, wrapper):
    out = lxml_html.tostring(root, encoding='unicode', method='html')
    return wrapper(out[out.index('>') + 1:out.rindex('<')])


def _replace_in_text_nodes(root, pattern, repl):
    """替换元素 text/tail 中匹配 pattern 的文字(不碰属性,跳过 style/script)。"""
    changed = False
    for el in root.iter():
        if el.tail and pattern.search(el.tail):
            el.tail = pattern.sub(repl, el.tail)
            changed = True
        if not isinstance(el.tag, str) or el.tag in _SKIP_TAGS:
            continue
        if el.text and pattern.search(el.text):
            el.text = pattern.sub(repl, el.text)
            changed = True
    return changed


def _drop_line_of(link):
    """删除链接所在的"一行"(同一父节点内,两个 <br> 之间的全部内容)。

    OdooBot 回复形如 "第一句<br>请查看<a odoo.com>文档</a>或<a>视频</a>。",
    只解链会留下 "请查看文档或视频" 这种指向不存在内容的半句话,整行删除更干净。
    该行是父节点唯一的一行时不删(避免整条消息被清空),返回 False。"""
    parent = link.getparent()
    children = list(parent)
    idx = children.index(link)
    before = [i for i in range(idx) if children[i].tag == 'br']
    after = [i for i in range(idx + 1, len(children)) if children[i].tag == 'br']
    if not before and not after:
        return False
    if before:
        # 连同行首的 <br> 一起删,行尾 <br> 留作上一行与下一行的分隔
        for child in children[before[-1]:after[0] if after else len(children)]:
            parent.remove(child)
    else:
        parent.text = children[after[0]].tail or ''
        for child in children[:after[0] + 1]:
            parent.remove(child)
    return True


_BOT_NAME_RE = re.compile(r'\bOdooBot\b', re.ASCII)


def debrand_bot_message(html_str, brand, bot_name):
    """OdooBot 消息去品牌:

    - 含 odoo.com 链接(文档/视频)的整行删除,无法整行删除时解链保留文字;
    - "OdooBot"(如 @OdooBot 提示)替换为机器人新名称;
    - 独立的 "Odoo" 品牌词替换为品牌名。
    未命中时原样返回入参;命中时返回与入参同类型(str/Markup)的结果。"""
    if not html_str or 'odoo' not in str(html_str).lower():
        return html_str
    root = _parse_fragment(html_str)
    if root is None:
        return html_str
    changed = False
    for link in list(root.iter('a')):
        if not _attached(link, root) or 'odoo.com' not in _link_href(link):
            continue
        if not _drop_line_of(link):
            _unwrap(link)
        changed = True
    if bot_name:
        changed |= _replace_in_text_nodes(root, _BOT_NAME_RE, bot_name)
    if brand:
        changed |= _replace_in_text_nodes(root, _BRAND_WORD_RE, brand)
    if not changed:
        return html_str
    return _serialize_fragment(root, html_str.__class__)


# 知识库新用户欢迎文章(knowledge.knowledge_article_user_onboarding)的品牌内容
_SOCIAL_HREF_RE = re.compile(
    r'(?:twitter|x|facebook|instagram|linkedin)\.com/(?:company/)?odoo\b'
    r'|youtube\.com/(?:channel/UCkQPikELWZFLgQNHd73jkdg|@?odoo\b)',
    re.IGNORECASE)
# Odoo 随 knowledge 模块附带的示例文件(Odoo Survival Guide.pdf)
_SHIPPED_FILE_MARK = '/knowledge/static/'


def _is_empty_paragraph(el):
    return (el.tag == 'p' and not _norm_text(el)
            and all(c.tag == 'br' for c in el if isinstance(c.tag, str)))


def _closest(el, tag, root):
    while el is not None and el is not root:
        if el.tag == tag:
            return el
        el = el.getparent()
    return None


def debrand_knowledge_onboarding(html_str, brand):
    """知识库新用户欢迎文章去品牌(与语言无关,按结构与链接识别):

    - 删除 Odoo 官方教学视频嵌入块,以及其上方列表中 "请看下方视频" 一项;
    - 删除 Odoo 附带的示例文件 "Odoo Survival Guide.pdf" 及介绍它的 /file 列表;
    - 删除文末 "关注我们的 X / YouTube / Facebook" 段落及其上方分隔线;
    - 独立的 "Odoo" 品牌词替换为品牌名;
    - 删除后合并连续的空段落。"""
    if not html_str:
        return html_str
    root = _parse_fragment(html_str)
    if root is None:
        return html_str
    changed = False

    for video in root.xpath('//*[@data-embedded="video"]'):
        prev = video.getprevious()
        if prev is not None and prev.tag == 'ul':
            items = prev.xpath('.//li[not(contains(concat(" ", @class, " "), " oe-nested "))]')
            if items:
                _drop(items[-1])
        _drop(video)
        changed = True

    for file_el in root.xpath('//*[@data-embedded="file"]'):
        if _SHIPPED_FILE_MARK not in (file_el.get('data-embedded-props') or ''):
            continue
        block = file_el.getparent() if file_el.getparent() is not root else file_el
        if block is not file_el and _norm_text(block):
            block = file_el
        prev = block.getprevious()
        if block is not file_el and prev is not None and prev.tag == 'ul':
            _drop(prev)
        _drop(block)
        changed = True

    for link in list(root.iter('a')):
        if not _attached(link, root) or not _SOCIAL_HREF_RE.search(link.get('href') or ''):
            continue
        block = _closest(link, 'p', root)
        if block is None:
            block = link
        prev = block.getprevious()
        if block is not link and prev is not None and prev.tag == 'hr':
            _drop(prev)
        _drop(block)
        changed = True

    if brand:
        changed |= _replace_in_text_nodes(root, _BRAND_WORD_RE, brand)
    if not changed:
        return html_str

    # 合并连续空段落,并去掉文末的空段落
    previous_empty = False
    for el in list(root):
        empty = _is_empty_paragraph(el)
        if empty and previous_empty:
            _drop(el)
        previous_empty = empty
    while len(root) and _is_empty_paragraph(root[-1]):
        _drop(root[-1])
    return _serialize_fragment(root, html_str.__class__)


def remove_empty_digest_tips(html_str):
    """digest 正文(digest.digest_mail_main)中,每条提示占一行
    ``table.global_layout > tbody > tr``。提示内容被白标清空后,该行只剩
    带内边距的空单元格,这里把没有任何可见内容的行删掉。"""
    if not html_str or 'global_layout' not in str(html_str):
        return html_str
    wrapper = html_str.__class__
    try:
        root = lxml_html.fragment_fromstring(str(html_str), create_parent='div')
    except (etree.ParserError, etree.XMLSyntaxError, ValueError):
        return html_str
    changed = False
    for table in root.xpath('//table[contains(concat(" ", normalize-space(@class), " "), " global_layout ")]'):
        for row in table.xpath('./tbody/tr | ./tr'):
            if _norm_text(row) or row.xpath('.//img | .//a | .//hr | .//input | .//button'):
                continue
            _drop(row)
            changed = True
    if not changed:
        return html_str
    out = lxml_html.tostring(root, encoding='unicode', method='html')
    return wrapper(out[out.index('>') + 1:out.rindex('<')])


def remove_odoo_branding(html_str):
    """返回移除 "Powered by Odoo" 区块后的 HTML。

    未命中时原样返回入参(不重排原文);命中时返回与入参同类型
    (str/Markup)的清理结果。可安全重复调用(幂等)。
    """
    if not html_str:
        return html_str
    source = str(html_str)
    low = source.lower()
    if ('odoo.com' not in low and 'powered by' not in low
            and not _ODOO_LOGO_SRC_RE.search(source)):
        return html_str
    wrapper = html_str.__class__  # 与核心 _replace_local_links 一致,保持 Markup 类型
    try:
        root = lxml_html.fragment_fromstring(source, create_parent='div')
    except (etree.ParserError, etree.XMLSyntaxError, ValueError):
        return wrapper(_FALLBACK_RE.sub('', source))

    changed = False
    for link in list(root.iter('a')):
        if link.getparent() is None or not _is_brand_link(link):
            continue
        block = _block_root(link, root)
        if block is link:
            # 链接与其他内容同处一行:
            # - 前面紧挨着固定品牌短语(如 digest 页脚 "Sent by Odoo – Unsubscribe"):
            #   删除短语+链接;
            # - 否则是句中的品牌链接:解链,保留文字,句子仍通顺。
            if not _drop_inline_brand(link):
                _unwrap(link)
            changed = True
            continue
        # 相邻的 <!-- POWERED BY --> 注释一并移除
        prev = block.getprevious()
        if (prev is not None and prev.tag is etree.Comment
                and _POWERED_COMMENT_RE.search(prev.text or '')):
            _drop(prev)
        _drop(block)
        changed = True
    # 邮件页眉里的 Odoo logo 图片:只删图片本身,保留所在单元格以免打乱版式
    for img in list(root.iter('img')):
        if _is_odoo_logo(img):
            _drop(img)
            changed = True
    # Odoo 官方 App 推广横幅(digest 邮件的 Odoo Mobile 下载区块等)
    for anchor in list(_promo_anchors(root)):
        if not _attached(anchor, root):
            continue  # 已随前一个锚点所在的区块一起删除
        block = _promo_block(anchor, root)
        if block is not anchor or anchor.tag == 'img':
            _drop(block)
            changed = True
    # 孤立残留的 POWERED BY 注释(如此前只删了文字的旧数据)
    for comment in list(root.iter(etree.Comment)):
        if _POWERED_COMMENT_RE.search(comment.text or ''):
            _drop(comment)
            changed = True
    if not changed:
        return html_str

    out = lxml_html.tostring(root, encoding='unicode', method='html')
    # 剥掉我们自己包上的 <div> 外壳
    start = out.index('>') + 1
    end = out.rindex('<')
    return wrapper(out[start:end])
