# -*- coding: utf-8 -*-
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor
from PySide6.QtCore import QRegularExpression

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#FF7B72")) # Pinkish Red
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "\\bdef\\b", "\\bclass\\b", "\\bimport\\b", "\\bfrom\\b",
            "\\bif\\b", "\\belif\\b", "\\belse\\b", "\\breturn\\b",
            "\\bfor\\b", "\\bwhile\\b", "\\bin\\b", "\\band\\b", "\\bor\\b",
            "\\bnot\\b", "\\bis\\b", "\\bpass\\b", "\\bbreak\\b", "\\bcontinue\\b"
        ]
        for word in keywords:
            self.highlighting_rules.append((QRegularExpression(word), keyword_format))

        # Builtins
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#79C0FF")) # Blue
        builtins = ["\\bTrue\\b", "\\bFalse\\b", "\\bNone\\b", "\\bprint\\b", "\\blen\\b"]
        for word in builtins:
            self.highlighting_rules.append((QRegularExpression(word), builtin_format))

        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#A5D6FF")) # Light Blue
        self.highlighting_rules.append((QRegularExpression("\".*?\""), string_format))
        self.highlighting_rules.append((QRegularExpression("'.*?'"), string_format))

        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#79C0FF"))
        self.highlighting_rules.append((QRegularExpression("\\b[0-9]+(\\.[0-9]+)?\\b"), number_format))

        # Comments
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#8B949E")) # Gray
        self.highlighting_rules.append((QRegularExpression("#[^\n]*"), self.comment_format))

        # Multi-line strings (tripe quotes)
        self.multi_line_comment_format = QTextCharFormat()
        self.multi_line_comment_format.setForeground(QColor("#A5D6FF"))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

        self.setCurrentBlockState(0)
        
        # Multiline string matching
        start_index = 0
        if self.previousBlockState() != 1:
            start_index = max(text.find("'''"), text.find('"""'))
            if text.find("'''") != -1 and text.find('"""') != -1:
                start_index = min(text.find("'''"), text.find('"""'))

        while start_index >= 0:
            end_index = max(text.find("'''", start_index + 3), text.find('"""', start_index + 3))
            if text.find("'''", start_index + 3) != -1 and text.find('"""', start_index + 3) != -1:
                 end_index = min(text.find("'''", start_index + 3), text.find('"""', start_index + 3))
                 
            if end_index == -1:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + 3
                
            self.setFormat(start_index, comment_length, self.multi_line_comment_format)
            
            if end_index != -1:
                start_index = max(text.find("'''", start_index + comment_length), text.find('"""', start_index + comment_length))
                if text.find("'''", start_index + comment_length) != -1 and text.find('"""', start_index + comment_length) != -1:
                     start_index = min(text.find("'''", start_index + comment_length), text.find('"""', start_index + comment_length))
            else:
                break

from PySide6.QtWidgets import QPlainTextEdit, QWidget
from PySide6.QtGui import QPainter, QColor, QFontMetrics
from PySide6.QtCore import Qt, QRect

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return self.codeEditor.lineNumberAreaSizeHint()

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.updateLineNumberAreaWidth(0)

    def lineNumberAreaWidth(self):
        digits = 1
        m = max(1, self.blockCount())
        while m >= 10:
            m /= 10
            digits += 1
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#0D1117"))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#484F58"))
                painter.drawText(0, int(top), self.lineNumberArea.width(), self.fontMetrics().height(),
                                 Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1
