#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# VÉLIGER
# Copyleft 2010 - Bruno C. Vellutini | organelas.com
# 
#TODO Inserir licença.
#
# Atualizado: 01 Jun 2010 01:06AM
'''Editor de metadados do banco de imagens do CEBIMar-USP.

Este programa abre imagens JPG, lê seus metadados (IPTC) e fornece uma
interface para editar estas informações. Os campos foram adaptados para o
propósito do banco, que é divulgar imagens com conteúdo biológico.

Campos editáveis: título, legenda, marcadores, táxon, espécie, especialista,
autor, direitos, tamanho, local, cidade, estado e país.

Centro de Biologia Marinha da Universidade de São Paulo.
'''

import os
import sys
import operator
import subprocess
import time
import re
import pickle

import pyexiv2

from PIL import Image
from shutil import copy
from iptcinfo import IPTCInfo

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtWebKit import *

import recursos

__author__ = 'Bruno Vellutini'
__copyright__ = 'Copyright 2010, CEBIMar-USP'
__credits__ = 'Bruno C. Vellutini'
__license__ = 'DEFINIR'
__version__ = '0.8.1'
__maintainer__ = 'Bruno Vellutini'
__email__ = 'organelas at gmail dot com'
__status__ = 'Development'


class MainWindow(QMainWindow):
    '''Janela principal do programa.

    Inicia as instâncias dos outros componentes e aguarda interação do usuário.
    '''
    def __init__(self):
        QMainWindow.__init__(self)
        # Definições
        global mainWidget
        global options
        mainWidget = MainTable(datalist, header)
        self.model = mainWidget.model
        self.automodels = AutoModels(autolists)
        options = PrefsDialog(self)
        self.help = ManualDialog(self)
        self.about = AboutDialog(self)
        self.copied = []
        # Tagcompleter
        self.tageditor = CompleterLineEdit(QLineEdit)
        self.tagcompleter = TagCompleter(self.automodels.tags,
                self.tageditor)
        self.tagcompleter.setCaseSensitivity(Qt.CaseInsensitive)
        self.tagcompleter.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.tagcompleter.setModelSorting(QCompleter.CaseInsensitivelySortedModel)
        # Dock com thumbnail
        self.dockThumb = DockThumb()
        self.thumbDockWidget = QDockWidget(u'Thumbnail', self)
        self.thumbDockWidget.setWidget(self.dockThumb)
        # Dock com lista de updates
        self.dockUnsaved = DockUnsaved()
        self.unsavedDockWidget = QDockWidget(u'Modificadas', self)
        self.unsavedDockWidget.setWidget(self.dockUnsaved)
        # Dock com geolocalização
        self.dockGeo = DockGeo(self)
        self.geoDockWidget = QDockWidget(u'Geolocalização', self)
        self.geoDockWidget.setWidget(self.dockGeo)
        # Dock com editor de metadados
        self.dockEditor = DockEditor(self)
        self.editorDockWidget = QDockWidget(u'Editor', self)
        self.editorDockWidget.setAllowedAreas(
                Qt.TopDockWidgetArea |
                Qt.BottomDockWidgetArea
                )
        self.editorDockWidget.setWidget(self.dockEditor)

        # Atribuições da MainWindow
        self.setCentralWidget(mainWidget)
        self.setWindowTitle(u'VÉLIGER - Editor de Metadados')
        self.setWindowIcon(QIcon(u':/appicon.svg'))
        self.statusBar().showMessage(u'Pronto para editar!', 2000)
        self.menubar = self.menuBar()

        # Ações do menu
        self.exit = QAction(QIcon(u':/desligar.png'),
                u'Sair', self)
        self.exit.setShortcut('Ctrl+Q')
        self.exit.setStatusTip(u'Fechar o programa')
        self.connect(self.exit, SIGNAL('triggered()'), SLOT('close()'))

        self.openFile = QAction(QIcon(u':/arquivo.png'),
                u'Abrir arquivo(s)', self)
        self.openFile.setShortcut('Ctrl+O')
        self.openFile.setStatusTip(u'Abrir imagens')
        self.connect(self.openFile, SIGNAL('triggered()'), self.openfile_dialog)

        self.openDir = QAction(QIcon(u':/pasta.png'),
                u'Abrir pasta(s)', self)
        self.openDir.setShortcut('Ctrl+D')
        self.openDir.setStatusTip(u'Abrir pasta')
        self.connect(self.openDir, SIGNAL('triggered()'), self.opendir_dialog)

        self.copyMeta = QAction(QIcon(u':/copiar.png'),
                u'Copiar metadados', self)
        self.copyMeta.setShortcut('Ctrl+C')
        self.copyMeta.setStatusTip(u'Copiar metadados da entrada selecionada')
        self.connect(self.copyMeta, SIGNAL('triggered()'), self.copydata)

        self.pasteMeta = QAction(QIcon(u':/colar.png'),
                u'Colar metadados', self)
        self.pasteMeta.setShortcut('Ctrl+V')
        self.pasteMeta.setStatusTip(
                u'Colar metadados na(s) entrada(s) selecionada(s)')
        self.connect(self.pasteMeta, SIGNAL('triggered()'), self.pastedata)

        self.delRow = QAction(QIcon(u':/deletar.png'),
                u'Deletar entrada(s)', self)
        self.delRow.setShortcut('Ctrl+W')
        self.delRow.setStatusTip(u'Deletar entrada')
        self.connect(self.delRow, SIGNAL('triggered()'), self.delcurrent)

        self.saveFile = QAction(QIcon(u':/salvar.png'),
                u'Salvar metadados', self)
        self.saveFile.setShortcut('Ctrl+S')
        self.saveFile.setStatusTip(u'Salvar metadados')
        self.connect(self.saveFile, SIGNAL('triggered()'),
                self.dockEditor.savedata)
        #salvo = lambda: self.changeStatus(u'Alterações salvas!')
        #self.saveFile.triggered.connect(salvo)

        self.writeMeta = QAction(QIcon(u':/gravar.png'),
                u'Gravar metadados', self)
        self.writeMeta.setShortcut('Ctrl+Shift+S')
        self.writeMeta.setStatusTip(u'Gravar metadados na imagem')
        self.connect(self.writeMeta, SIGNAL('triggered()'),
                self.dockUnsaved.writeselected)
        salvo = lambda: self.changeStatus(
                u'Metadados gravados na(s) imagem(ns)')
        self.writeMeta.triggered.connect(salvo)

        self.delAll = QAction(QIcon(u':/deletar.png'),
                u'Limpar tabela', self)
        self.delAll.setStatusTip(u'Deletar todas as entradas')
        self.connect(self.delAll, SIGNAL('triggered()'), self.cleartable)

        self.convertChar = QAction(QIcon(u':/conversor.png'),
                u'Converter codificação (Latin-1 -> UTF-8)', self)
        self.convertChar.setStatusTip(
                u'Converter metadados das imagens selecionadas de Latin-1' +
                ' para UTF-8, use com cautela')
        self.connect(self.convertChar, SIGNAL('triggered()'),
                self.charconverter)

        self.openPref = QAction(QIcon(u':/options.png'),
                u'Opções', self)
        self.openPref.setStatusTip(u'Abrir opções do programa')
        self.connect(self.openPref, SIGNAL('triggered()'),
                self.openpref_dialog)

        self.openManual = QAction(QIcon(u':/manual.png'),
                u'Manual', self)
        self.openManual.setStatusTip(u'Abrir manual de instruções do programa')
        self.connect(self.openManual, SIGNAL('triggered()'),
                self.openmanual_dialog)

        self.openAbout = QAction(QIcon(u':/sobre.png'),
                u'Sobre', self)
        self.openAbout.setStatusTip(u'Sobre o programa')
        self.connect(self.openAbout, SIGNAL('triggered()'),
                self.openabout_dialog)

        # Toggle dock widgets
        self.toggleThumb = self.thumbDockWidget.toggleViewAction()
        self.toggleThumb.setShortcut('Shift+T')
        self.toggleThumb.setStatusTip(u'Esconde ou mostra o dock com thumbnails')
        self.toggleGeo = self.geoDockWidget.toggleViewAction()
        self.toggleGeo.setShortcut('Shift+G')
        self.toggleGeo.setStatusTip(u'Esconde ou mostra o dock com geolocalização')

        self.toggleEditor = self.editorDockWidget.toggleViewAction()
        self.toggleEditor.setShortcut('Shift+E')
        self.toggleEditor.setStatusTip(u'Esconde ou mostra o dock com o editor')

        self.toggleUnsaved = self.unsavedDockWidget.toggleViewAction()
        self.toggleUnsaved.setShortcut('Shift+U')
        self.toggleUnsaved.setStatusTip(u'Esconde ou mostra o dock com modificadas')

        # Menu
        self.arquivo = self.menubar.addMenu('&Arquivo')
        self.arquivo.addAction(self.openFile)
        self.arquivo.addAction(self.openDir)
        self.arquivo.addSeparator()
        self.arquivo.addAction(self.writeMeta)
        self.arquivo.addSeparator()
        self.arquivo.addAction(self.openPref)
        self.arquivo.addSeparator()
        self.arquivo.addAction(self.exit)

        self.editar = self.menubar.addMenu('&Editar')
        self.editar.addAction(self.delAll)
        self.editar.addSeparator()
        self.editar.addAction(self.copyMeta)
        self.editar.addAction(self.pasteMeta)
        self.editar.addAction(self.saveFile)
        self.editar.addAction(self.delRow)
        self.editar.addSeparator()
        self.editar.addAction(self.convertChar)
        self.editar.addSeparator()
        
        self.janela = self.menubar.addMenu('&Janela')
        self.janela.addAction(self.toggleEditor)
        self.janela.addAction(self.toggleThumb)
        self.janela.addAction(self.toggleGeo)
        self.janela.addAction(self.toggleUnsaved)

        self.ajuda = self.menubar.addMenu('&Ajuda')
        self.ajuda.addAction(self.openManual)
        self.ajuda.addSeparator()
        self.ajuda.addAction(self.openAbout)

        # Toolbar
        self.toolbar = self.addToolBar('Ações')
        self.toolbar.addAction(self.openFile)
        self.toolbar.addAction(self.openDir)
        self.toolbar.addAction(self.copyMeta)
        self.toolbar.addAction(self.pasteMeta)
        self.toolbar.addAction(self.saveFile)
        self.toolbar.addAction(self.delRow)
        self.toolbar = self.addToolBar('Sair')
        self.toolbar.addAction(self.exit)

        # Docks
        self.addDockWidget(Qt.RightDockWidgetArea, self.thumbDockWidget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.geoDockWidget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.unsavedDockWidget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.editorDockWidget)
        self.tabifyDockWidget(self.unsavedDockWidget, self.thumbDockWidget)
        self.tabifyDockWidget(self.geoDockWidget, self.editorDockWidget)
        self.setTabPosition(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea,
                QTabWidget.North)
        #self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        self.connect(
                self.geoDockWidget,
                SIGNAL('visibilityChanged(bool)'),
                self.istab_selected
                )
        
        self.connect(
                self.dockUnsaved,
                SIGNAL('commitMeta(entries)'),
                self.commitmeta
                )

        self.connect(
                self.dockUnsaved,
                SIGNAL('syncSelection(filename)'),
                self.setselection
                )

        self.connect(self.tageditor,
                SIGNAL('text_changed(PyQt_PyObject, PyQt_PyObject)'),
                self.tagcompleter.update)
        self.connect(self.tagcompleter, SIGNAL('activated(QString)'),
                self.tageditor.complete_text)

        self.readsettings()

    def istab_selected(self, visible):
        self.emit(SIGNAL('ismapSelected(visible)'), visible)

    def copydata(self):
        '''Copia metadados da entrada selecionada.'''
        if self.dockEditor.values:
            values = self.dockEditor.values
            self.copied = [value[1] for value in values]
            self.changeStatus(u'Metadados copiados de %s' % values[0][1], 5000)

    def pastedata(self):
        '''Cola metadados na(s) entrada(s) selecionada(s).'''
        indexes = mainWidget.selectedIndexes()
        rows = [index.row() for index in indexes]
        rows = list(set(rows))

        # Slices dos índices selecionados.
        nrows = len(rows)
        si = 0
        st = nrows
        
        # Título
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[1]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Legenda
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[2]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Marcadores
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[3]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Táxon
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[4]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Espécie
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[5]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Especialista
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[6]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Autor
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[7]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Direitos
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[8]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Tamanho
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[9]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Local
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[10]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Cidade
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[11]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Estado
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[12]),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Estado
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.copied[13]),
                    Qt.EditRole)

        mainWidget.setFocus(Qt.OtherFocusReason)
        self.changeStatus(u'%d entradas alteradas!' % nrows, 5000)

    def openpref_dialog(self):
        '''Abre janela de opções.'''
        options.exec_()

    def openmanual_dialog(self):
        '''Abre janela do manual de instruções.'''
        self.help.exec_()

    def openabout_dialog(self):
        '''Abre janela sobre o programa.'''
        self.about.exec_()

    def charconverter(self):
        '''Converte codificação de Latin-1 para UTF-8.

        Pega a seleção da lista de imagens modificadas e procura a linha
        correspondente na tabela principal. Se o item não for encontrado o item
        na lista é apagado.
        '''

        critical = QMessageBox.critical(self,
                u'Cuidado!',
                u'As imagens selecionadas serão convertidas! ' \
                        u'Selecione apenas imagens que estejam com ' \
                        u'problemas na codificação de caracteres ' \
                        u'especiais (ç, à, ã, á)! Se nenhuma entrada ' \
                        u'estiver selecionada todas as imagens da ' \
                        u'tabela serão convertidas! Faça um backup das ' \
                        u'suas imagens antes de executar a conversão ' \
                        u'(é sério). Deseja prosseguir e converter os ' \
                        u'metadados da imagem de Latin-1 para UTF-8?',
                QMessageBox.Yes,
                QMessageBox.No)
        if critical == QMessageBox.Yes:
            entries = []
            n_all = 0
            indexes = mainWidget.selectionModel.selectedRows()
            if indexes:
                indexes = [index.row() for index in indexes]
                for row in indexes:
                    index = mainWidget.model.index(row, 0, QModelIndex())
                    filepath = mainWidget.model.data(index, Qt.DisplayRole)
                    entries.append(filepath.toString())
                self.delcurrent()
            else:
                for entry in self.model.mydata:
                    entries.append(entry[0])
                self.cleartable()
            for filepath in entries:
                entrymeta = self.createmeta(filepath, 'latin-1')
                self.model.insert_rows(0, 1, QModelIndex(), entrymeta)
                self.writemeta(entrymeta)
                n_all += 1
            self.changeStatus(
                    u'Metadados de %d figuras convertidos para UTF-8'
                    % n_all)
        else:
            self.changeStatus(u'Nenhuma imagem foi modificada')

    def setselection(self, filename):
        '''Sincroniza seleção entre lista e tabela principal.

        Pega a seleção da lista de imagens modificadas e procura a linha
        correspondente na tabela principal. Se o item não for encontrado o item
        na lista é apagado.
        '''
        index = self.model.index(0, 0, QModelIndex())
        matches = self.model.match(index, 0, filename, -1,
                Qt.MatchContains)
        if len(matches) == 1:
            match = matches[0]
            mainWidget.selectRow(match.row())
        elif len(matches) == 0:
            mainWidget.selectionModel.clearSelection()
            mainWidget.emitlost(filename)
            self.changeStatus(u'%s não foi encontrada, importe-a novamente' %
                    filename, 10000)

    def commitmeta(self, entries):
        '''Grava os metadados modificados na imagem.
        
        Pega lista de imagens modificadas, procura entrada na tabela principal
        e retorna os metadados. Chama função que gravará estes metadados na
        imagem. Chama função que emitirá o sinal avisando a gravação foi
        completada com sucesso.        
        '''
        if entries:
            for entry in entries:
                index = self.model.index(0, 0, QModelIndex())
                matches = self.model.match(index, 0, entry, -1,
                        Qt.MatchContains)
                if len(matches) == 1:
                    values = []
                    match = matches[0]
                    for col in xrange(mainWidget.ncols):
                        index = self.model.index(match.row(), col, QModelIndex())
                        value = self.model.data(index, Qt.DisplayRole)
                        values.append(unicode(value.toString()))
                    filename = os.path.basename(values[0])
                    self.changeStatus(u'Gravando metadados em %s...' % filename)
                    write = self.writemeta(values)
                    if write == 0:
                        self.changeStatus(u'%s atualizado!' % filename)
                        continue
                    else:
                        break
            if write == 0:
                mainWidget.emitsaved()
            else:
                self.changeStatus(u'%s deu erro!' % filename, 5000)
                critical = QMessageBox()
                critical.setWindowTitle(u'Erro de gravação!')
                critical.setText(u'Metadados não foram gravados.')
                critical.setInformativeText(
                        u'%s pode ter mudado de local, nome ou ' % filename +
                        'estar protegido contra gravação. Tente importá-lo ' +
                        'novamente. O arquivo será retirado da lista de ' +
                        'imagens modificadas. Deseja deletar a entrada da ' +
                        'tabela principal também?')
                critical.setIcon(QMessageBox.Critical)
                critical.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                critical.exec_()
                self.setselection(filename)
                mainWidget.emitlost(filename)
                if critical == QMessageBox.Yes:
                    self.delcurrent()
        else:
            self.changeStatus(u'Lista de entradas modificadas está vazia')

    def writemeta(self, values):
        '''Grava os metadados no arquivo.'''
        print 'Gravando metadados pelo IPTCinfo...'
        # Criar objeto com metadados
        info = IPTCInfo(values[0])
        try:
            info.data['object name'] = values[1]                    # title
            info.data['caption/abstract'] = values[2]               # caption
            info.data['headline'] = values[4]                       # category
            info.data['original transmission reference'] = values[5]# sp
            info.data['source'] = values[6]                         # source
            info.data['by-line'] = values[7]                        # author
            info.data['copyright notice'] = values[8]               # copyright
            info.data['special instructions'] = values[9]           # scale
            info.data['sub-location'] = values[10]                  # sublocation
            info.data['city'] = values[11]                          # city
            info.data['province/state'] = values[12]                # state
            info.data['country/primary location name'] = values[13] # country

            # Lista com keywords
            if values[3] == '' or values[3] is None:
                info.keywords = []                                  # keywords
            else:
                keywords = values[3].split(',')
                keywords = [keyword.lower().strip() for keyword in keywords if
                        keyword.strip() != '']
                info.data['keywords'] = list(set(keywords))         # keywords
            info.save()
        except IOError:
            #FIXME Erro não está aparecendo...
            print '\nOcorreu algum erro. '
            self.changeStatus(u'ERRO!', 10000)
            critical = QMessageBox()
            critical.setWindowTitle(u'Erro!')
            critical.setText(u'Verifique se o IPTCinfo está bem.')
            critical.setIcon(QMessageBox.Critical)
            critical.exec_()
        else:
            # Salva cache
            self.cachetable()
            return 0

    def exiftool(self, values):
        '''Grava os metadados no arquivo.

        Usa subprocesso para chamar o exiftool, que gravará os metadados
        modificados na imagem.

        Função não utilizada, mas pode ser útil algum dia.
        '''
        try:
            shellcall = [
                    'exiftool',
                    '-overwrite_original',
                    '-ObjectName=%s' % values[1],
                    '-Caption-Abstract=%s' % values[2],
                    '-Headline=%s' % values[4],
                    '-OriginalTransmissionReference=%s' % values[5],
                    '-Source=%s' % values[6],
                    '-By-line=%s' % values[7],
                    '-CopyrightNotice=%s' % values[8],
                    '-SpecialInstructions=%s' % values[9],
                    '-Sub-location=%s' % values[10],
                    '-City=%s' % values[11],
                    '-Province-State=%s' % values[12],
                    '-Country-PrimaryLocationName=%s' % values[13],
                    '-UsageTerms="Creative Commons BY-NC-SA"',
                    ]
            # Lista com keywords
            if values[3] == '' or values[3] is None:
                shellcall.append('-Keywords=')
            else:
                keywords = values[3].split(', ')
                for keyword in keywords:
                    shellcall.append('-Keywords=%s' % keyword.lower())
            shellcall.append(values[0])
            # Executando o comando completo
            stdout = subprocess.call(shellcall)
        except IOError:
            print '\nOcorreu algum erro. ',
            print 'Verifique se o ExifTool está instalado.'
            self.changeStatus(u'ERRO: Verifique se o exiftool está instalado',
                    10000)
            critical = QMessageBox()
            critical.setWindowTitle(u'Erro!')
            critical.setText(u'Verifique se o exiftool está instalado.')
            critical.setIcon(QMessageBox.Critical)
            critical.exec_()
        else:
            # Salva cache
            self.cachetable()
            return stdout

    def changeStatus(self, status, duration=2000):
        '''Muda a mensagem de status da janela principal.'''
        self.statusBar().showMessage(status, duration)

    def openfile_dialog(self):
        '''Abre janela para escolher arquivos.

        Para selecionar arquivo(s) terminados em .jpg.
        '''
        self.openfile = QFileDialog()
        filepaths = self.openfile.getOpenFileNames(self, 'Selecionar imagem(ns)',
                self.last_openfile, 'Images (*.jpg *.jpeg *.JPG *.JPEG)')
        if filepaths:
            self.last_openfile = os.path.dirname(unicode(filepaths[0]))
            n_all = len(filepaths)
            n_new = 0
            n_dup = 0
            t0 = time.time()
            self.changeStatus(u'Importando %d imagens...' % n_all)
            for filepath in filepaths:
                filename = os.path.basename(unicode(filepath))
                print filename
                matches = self.matchfinder(filename)
                if len(matches) == 0:
                    entrymeta = self.createmeta(filepath)
                    self.model.insert_rows(0, 1, QModelIndex(), entrymeta)
                    n_new += 1
                else:
                    n_dup += 1
                    pass
            t1 = time.time()
            t = t1 - t0
            self.changeStatus(u'%d imagens analisadas em %.2f s,' % (n_all, t) +
                    u' %d novas e %d duplicadas' % (n_new, n_dup), 10000)
        # Salva cache
        self.cachetable()

    def opendir_dialog(self):
        '''Abre janela para selecionar uma pasta.
        
        Chama a função para varrer a pasta selecionada.
        '''
        self.opendir = QFileDialog()
        folder = self.opendir.getExistingDirectory(
                self,
                'Selecione uma pasta',
                self.last_opendir,
                QFileDialog.ShowDirsOnly
                )
        if folder:
            self.last_opendir = unicode(folder)
            self.imgfinder(unicode(folder))

    def imgfinder(self, folder):
        '''Busca recursivamente imagens na pasta selecionada.
        
        É possível definir as extensões a serem procuradas. Quando um arquivo é
        encontrado ele verifica se já está na tabela. Se não estiver, ele chama
        a função para extrair os metadados e insere uma nova entrada.
        '''
        n_all = 0
        n_new = 0
        n_dup = 0

        # Tupla para o endswith()
        extensions = ('jpg', 'JPG', 'jpeg', 'JPEG')

        t0 = time.time()
        
        # Buscador de imagens em ação
        for root, dirs, files in os.walk(folder):
            for filename in files:
                if filename.endswith(extensions):
                    matches = self.matchfinder(filename)
                    if len(matches) == 0:
                        filepath = os.path.join(root, filename)
                        timestamp = time.strftime('%d/%m/%Y %I:%M:%S %p',
                                time.localtime(os.path.getmtime(filepath)))                    
                        entrymeta = self.createmeta(filepath)
                        self.model.insert_rows(0, 1, QModelIndex(), entrymeta)
                        n_new += 1
                    else:
                        n_dup += 1
                        pass
                    n_all += 1
        else:	# Se o número máximo de imagens for atingido, finalizar
            t1 = time.time()
            t = t1 - t0
            self.changeStatus(u'%d imagens analisadas em %.2f s,' % (n_all, t) +
                    u' %d novas e %d duplicadas' % (n_new, n_dup), 10000)
        # Salva cache
        self.cachetable()
            
    def createmeta(self, filepath, charset='utf-8'):
        '''Define as variáveis extraídas dos metadados (IPTC) da imagem.

        Usa a biblioteca do arquivo iptcinfo.py e retorna lista com valores.
        '''
        filepath = unicode(filepath)
        filename = os.path.basename(filepath)
        self.changeStatus(u'Lendo os metadados de %s e criando variáveis...' %
                filename)
        # Criar objeto com metadados
        info = IPTCInfo(filepath, True, charset)
        # Checando se o arquivo tem dados IPTC
        if len(info.data) < 4:
            print u'%s não tem dados IPTC!' % filename

        # Definindo as variáveis                            # IPTC
        title = info.data['object name']                    # 5
        keywords = info.data['keywords']                    # 25
        author = info.data['by-line']                       # 80
        city = info.data['city']                            # 90
        sublocation = info.data['sub-location']             # 92
        state = info.data['province/state']                 # 95
        country = info.data['country/primary location name']# 101
        category = info.data['headline']                    # 105
        copyright = info.data['copyright notice']           # 116
        caption = info.data['caption/abstract']             # 120
        sp = info.data['original transmission reference']   # 103
        scale = info.data['special instructions']           # 40
        source = info.data['source']                        # 115

        # Criando timestamp
        timestamp = time.strftime('%d/%m/%Y %H:%M:%S',
                time.localtime(os.path.getmtime(filepath)))
        # Cria a lista para tabela da interface
        entrymeta = [
                filepath,
                title,
                caption,
                ', '.join(keywords),
                category,
                sp,
                source,
                author,
                copyright,
                scale,
                sublocation,
                city,
                state,
                country,
                timestamp,
                ]
        if entrymeta[3] != '':
            entrymeta[3] = entrymeta[3] + ', '
        else:
            pass
        # Converte valores dos metadados vazios (None) para string em branco
        # FIXME Checar se isso está funcionando direito...
        for index in [index for index, field in enumerate(entrymeta) if \
                field is None]:
            field = u''
            entrymeta[index] = field
        else:
            pass

        self.createthumbs(filepath)

        return entrymeta

    def createthumbs(self, filepath):
        '''Cria thumbnails para as fotos novas.'''

        size = 400, 400
        hasdir = os.path.isdir(thumbdir)
        if hasdir is True:
            pass
        else:
            os.mkdir(thumbdir)
        filename = os.path.basename(filepath)
        thumbs = os.listdir(thumbdir)
        thumbpath = os.path.join(thumbdir, filename)
        if filename in thumbs:
            pass
        else:
            copy(filepath, thumbdir)
            self.changeStatus('%s copiado para %s' % (filename, thumbdir))
            try:
                im = Image.open(thumbpath)
                im.thumbnail(size, Image.ANTIALIAS)
                im.save(thumbpath, 'JPEG')
            except IOError:
                print 'Não consegui criar o thumbnail...'

    def matchfinder(self, candidate):
        '''Verifica se entrada já está na tabela.

        O candidato pode ser o nome do arquivo (string) ou a entrada
        selecionada da tabela (lista). Retorna uma lista com duplicatas ou
        lista vazia caso nenhuma seja encontrada.
        '''
        index = self.model.index(0, 0, QModelIndex())
        if isinstance(candidate, list):
            value = os.path.basename(unicode(entry[0]))
            matches = self.model.match(index, 0, value, -1, Qt.MatchContains)
        else:
            matches = self.model.match(index, 0, candidate, -1, Qt.MatchContains)
        return matches

    def delcurrent(self):
        '''Deleta a(s) entrada(s) selecionada(s) da tabela.
        
        Verifica se a entrada a ser deletada está na lista de imagens
        modificadas. Se estiver, chama janela para o usuário decidir se quer
        apagar a entrada mesmo sem as modificações terem sido gravadas na
        imagem. Caso a resposta seja positiva a entrada será apagada e retirada
        da lista de imagens modificadas.
        '''
        indexes = mainWidget.selectionModel.selectedRows()
        if indexes:
            n_del = 0
            # Cria lista com linhas a serem deletadas
            indexes = [index.row() for index in indexes]
            unsaved = []
            for row in indexes:
                index = mainWidget.model.index(row, 0, QModelIndex())
                filepath = mainWidget.model.data(index, Qt.DisplayRole)
                filename = os.path.basename(unicode(filepath.toString()))
                if filename in self.dockUnsaved.mylist:
                    unsaved.append(filename)
                else:
                    continue
            #TODO Tem algum jeito de melhorar esse função?
            if len(unsaved) > 0:
                warning = QMessageBox.warning(
                        self,
                        u'Atenção!',
                        u'As alterações não foram gravadas nas imagens.' \
                                u' Deseja apagá-las mesmo assim?',
                        QMessageBox.Yes,
                        QMessageBox.No)
                if warning == QMessageBox.Yes:
                    for filename in unsaved:
                        mainWidget.emitlost(filename)
                    # Ordem decrescente previne contra o erro 'out of range'
                    # na hora de deletar diversas entradas
                    indexes.sort()
                    indexes.reverse()
                    for index in indexes:
                        self.model.remove_rows(index, 1, QModelIndex())
                        n_del += 1
                    self.changeStatus(u'%d entradas deletadas' % n_del)
                else:
                    self.changeStatus(
                            u'Nenhuma entrada apagada, grave as alterações',
                            10000
                            )
            else:
                # Ordem decrescente previne contra o erro 'out of range'
                # na hora de deletar diversas entradas
                indexes.sort()
                indexes.reverse()
                for index in indexes:
                    self.model.remove_rows(index, 1, QModelIndex())
                    n_del += 1
                self.changeStatus(u'%d entradas deletadas' % n_del)
        else:
            self.changeStatus(u'Nenhuma entrada selecionada')
        # Salva cache
        self.cachetable()

    def cleartable(self):
        '''Remove todas as entradas da tabela.

        Antes de deletar checa se existem imagens não-salvas na lista.
        '''
        # Ver se não dá pra melhorar...
        if len(self.dockUnsaved.mylist) == 0:
            rows = self.model.rowCount(self.model)
            if rows > 0:
                self.model.remove_rows(0, rows, QModelIndex())
                self.changeStatus(u'%d entradas deletadas' % rows)
            else:
                self.changeStatus(u'Nenhuma entrada selecionada')
        else:
            warning = QMessageBox.warning(
                    self,
                    u'Atenção!',
                    u'As alterações não foram gravadas nas imagens.' \
                            u' Deseja apagá-las mesmo assim?',
                    QMessageBox.Yes,
                    QMessageBox.No)
            if warning == QMessageBox.Yes:
                rows = self.model.rowCount(self.model)
                if rows > 0:
                    self.model.remove_rows(0, rows, QModelIndex())
                    mainWidget.emitsaved()
                    self.changeStatus(u'%d entradas deletadas' % rows)
                else:
                    self.changeStatus(u'Nenhuma entrada selecionada')
        # Salva cache
        self.cachetable()

    def cachetable(self):
        '''Salva estado atual dos dados em arquivos externos.
        
        Cria backup dos conteúdos da tabela e da lista de imagens modificadas.
        '''
        print 'Backup...',
        #self.changeStatus(u'Salvando backup...')
        # Tabela
        tablecache = open(tablepickle, 'wb')
        entries = mainWidget.model.mydata
        pickle.dump(entries, tablecache)
        tablecache.close()
        # Lista
        listcache = open(listpickle, 'wb')
        entries = self.dockUnsaved.mylist
        pickle.dump(entries, listcache)
        listcache.close()
        # Completes 
        autocache = open(autopickle, 'wb')
        for k, v in autolists.iteritems():
            comps = []
            list = eval('self.automodels.' + k + '.stringList()')
            for i in list:
                comps.append(i)
            autolists[k] = comps
        pickle.dump(autolists, autocache)
        autocache.close()
        print 'pronto!'
        #self.changeStatus(u'Salvando backup... pronto!')

    def readsettings(self):
        '''Lê o estado anterior do aplicativo durante a inicialização.'''
        settings = QSettings()

        settings.beginGroup('main')
        self.resize(settings.value('size', QSize(1000, 740)).toSize())
        self.move(settings.value('position', QPoint(200, 0)).toPoint())
        self.last_openfile = settings.value('openfile').toString()
        self.last_opendir = settings.value('opendir').toString()
        settings.endGroup()

    def writesettings(self):
        '''Salva estado atual do aplicativo.'''
        settings = QSettings()

        settings.beginGroup('main')
        settings.setValue('size', self.size())
        settings.setValue('position', self.pos())
        settings.setValue('openfile', self.last_openfile)
        settings.setValue('opendir', self.last_opendir)
        settings.endGroup()

    def closeEvent(self, event):
        '''O que fazer quando o programa for fechado.'''
        self.cachetable()
        self.writesettings()
        event.accept()
        #reply = QMessageBox.question(
        #        self,
        #        u'Atenção!',
        #        u'O programa será finalizado.\nVocê está certo disso?',
        #        QMessageBox.Yes,
        #        QMessageBox.No
        #        )
        #if reply == QMessageBox.Yes:
        #    self.cachetable()
        #    self.writesettings()
        #    event.accept()
        #else:
        #    event.ignore()


class ManualDialog(QDialog):
    '''Janela do manual de instruções.'''
    def __init__(self, parent):
        QDialog.__init__(self, parent)


class AboutDialog(QDialog):
    '''Janela com informações sobre o programa.'''
    def __init__(self, parent):
        QDialog.__init__(self, parent)


class PrefsDialog(QDialog):
    '''Janela de preferências.'''
    def __init__(self, parent):
        QDialog.__init__(self, parent)

        self.automodels = parent.automodels

        self.geral = PrefsGerais()
        self.autocomplete = EditCompletion(self)

        self.tabwidget = QTabWidget()
        self.tabwidget.addTab(self.geral, u'&Gerais')
        self.tabwidget.addTab(self.autocomplete, u'&Autocompletador')

        self.buttons = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.connect(self.buttons, SIGNAL('accepted()'), self,
                SLOT('accept()'))
        self.connect(self.buttons, SIGNAL('accepted()'), self.emitrebuild)
        self.connect(self.buttons, SIGNAL('rejected()'), self,
                SLOT('reject()'))

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tabwidget)
        self.layout.addWidget(self.buttons)
        self.setLayout(self.layout)

        self.setWindowTitle(u'Opções')

    def emitrebuild(self):
        '''Emite sinal com modelos atualizados e ordenados.'''
        models = dir(self.automodels)
        excludes = ['__doc__', '__init__', '__module__', 'autolists']
        for ex in excludes:
            models.remove(ex)
        for model in models:
            eval('self.automodels.' + model + '.sort(0)')
        self.emit(SIGNAL('rebuildcomplete(models)'), self.automodels)


class EditCompletion(QWidget):
    '''Editor dos valores para autocompletar campos de edição.'''
    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.lists = [
                u'Marcadores',
                u'Taxa',
                u'Espécies',
                u'Especialistas',
                u'Autores',
                u'Direitos',
                u'Locais',
                u'Cidades',
                u'Estados',
                u'Países',
                ]
        self.automenu = QComboBox()
        self.automenu.addItems(self.lists)

        self.model = parent.automodels.tags
        self.view = QListView()
        self.view.setModel(self.model)
        self.view.setAlternatingRowColors(True)

        self.automodels = parent.automodels

        self.popmodels = QPushButton(
                u'&Extrair valores das imagens abertas', self)

        self.buttonbox = QWidget()
        self.insert = QPushButton(u'&Inserir', self)
        self.remove = QPushButton(u'&Remover', self)
        self.buttonhbox = QHBoxLayout()
        self.buttonhbox.addWidget(self.remove)
        self.buttonhbox.addWidget(self.insert)
        self.buttonbox.setLayout(self.buttonhbox)

        self.viewvbox = QVBoxLayout()
        self.viewvbox.addWidget(self.automenu)
        self.viewvbox.addWidget(self.buttonbox)
        self.viewvbox.addWidget(self.view)
        self.viewvbox.addWidget(self.popmodels)
        self.setLayout(self.viewvbox)

        self.connect(self.insert, SIGNAL('clicked()'),
                self.insertrow)
        self.connect(self.remove, SIGNAL('clicked()'),
                self.removerow)
        self.connect(self.popmodels, SIGNAL('clicked()'),
                self.populate)
        self.connect(self.automenu, SIGNAL('currentIndexChanged(QString)'),
                self.buildview)

    def buildview(self, modellist):
        '''Gera view do modelo escolhido.'''
        if modellist == u'Marcadores':
            self.model = self.automodels.tags
        elif modellist == u'Taxa':
            self.model = self.automodels.taxa
        elif modellist == u'Espécies':
            self.model = self.automodels.spp
        elif modellist == u'Especialistas':
            self.model = self.automodels.sources
        elif modellist == u'Autores':
            self.model = self.automodels.authors
        elif modellist == u'Direitos':
            self.model = self.automodels.rights
        elif modellist == u'Locais':
            self.model = self.automodels.locations
        elif modellist == u'Cidades':
            self.model = self.automodels.cities
        elif modellist == u'Estados':
            self.model = self.automodels.states
        elif modellist == u'Países':
            self.model = self.automodels.countries
        self.view.setModel(self.model)

    def insertrow(self):
        '''Insere linha no modelo.'''
        self.model.insertRows(0, 1, QModelIndex())
        
    def removerow(self):
        '''Remove linha do modelo.'''
        indexes = self.view.selectedIndexes()
        for index in indexes:
            self.model.removeRows(index.row(), 1, QModelIndex())

    def populate(self):
        '''Extrai valores das fotos e popula modelo.'''
        modellist = self.model.stringList()
        setlist = set(modellist)
        current = self.automenu.currentText()
        if current == u'Marcadores':
            col = 3
        elif current == u'Taxa':
            col = 4
        elif current == u'Espécies':
            col = 5
        elif current == u'Especialistas':
            col = 6
        elif current == u'Autores':
            col = 7
        elif current == u'Direitos':
            col = 8
        elif current == u'Locais':
            col = 10
        elif current == u'Cidades':
            col = 11
        elif current == u'Estados':
            col = 12
        elif current == u'Países':
            col = 13

        rows = mainWidget.model.rowCount(mainWidget.model)

        if col == 3:
            all = []
            for row in xrange(rows):
                index = mainWidget.model.index(row, col, QModelIndex())
                value = mainWidget.model.data(index, Qt.DisplayRole)
                if unicode(value.toString()) != '':
                    taglist = value.toString().split(',')
                    for tag in taglist:
                        if tag.trimmed() != '':
                            all.append(tag.trimmed())
        else:
            all = []
            for row in xrange(rows):
                index = mainWidget.model.index(row, col, QModelIndex())
                value = mainWidget.model.data(index, Qt.DisplayRole)
                if unicode(value.toString()) != '':
                    all.append(value.toString())

        setall = set(all)
        finalset = setlist | setall
        self.model.setStringList(list(finalset))
        self.view.setModel(self.model)


class PrefsGerais(QWidget):
    '''Opções gerais do programa.'''
    def __init__(self):
        QWidget.__init__(self)


class MainTable(QTableView):
    '''Tabela principal com entradas.'''
    def __init__(self, datalist, header, *args):
        QTableView.__init__(self, *args)

        self.header = header
        self.mydata = datalist

        self.model = TableModel(self, self.mydata, self.header)
        self.setModel(self.model)
        self.selectionModel = self.selectionModel()
        self.selectionModel.clearSelection()

        self.nrows = self.model.rowCount(self.model)
        self.ncols = self.model.columnCount(self.model)

        vh = self.verticalHeader()
        vh.setVisible(False)
        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)

        self.cols_resized = [1, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
        for col in self.cols_resized:
            self.resizeColumnToContents(col)
        self.setColumnWidth(1, 250)
        self.setColumnWidth(2, 200)
        self.setColumnWidth(3, 250)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(self.SelectRows)
        self.setSortingEnabled(True)
        self.hideColumn(0)
        self.hideColumn(14)
        self.selecteditems = []

        # Para limpar entrada dumb na inicialização
        if self.nrows == 1 and self.mydata[0][0] == '':
            self.model.remove_rows(0, 1, QModelIndex())

        #TODO Função obsoleta, ver se tem algo para aproveitar.
        #self.connect(
        #        self.selectionModel,
        #        SIGNAL('selectionChanged(QItemSelection, QItemSelection)'),
        #        self.update_selection)

        self.connect(
                self.selectionModel,
                SIGNAL('currentChanged(QModelIndex, QModelIndex)'),
                self.changecurrent)
        
        #XXX Não utilizado
        self.connect(
                self.verticalScrollBar(),
                SIGNAL('valueChanged(int)'),
                self.outputrows
                )

        self.connect(
                self.model,
                SIGNAL('dataChanged(index, value, oldvalue)'),
                self.editmultiple
                )

        self.connect(
                self.model,
                SIGNAL('dataChanged(index, value, oldvalue)'),
                self.resizecols
                )

    def editmultiple(self, index, value, oldvalue):
        '''Edita outras linhas selecionadas.'''
        rows = self.selectionModel.selectedRows()
        if len(rows) > 1:
            for row in rows:
                self.selectionModel.clearSelection()
                index = self.model.index(row.row(), index.column(), QModelIndex())
                self.model.setData(index, value, Qt.EditRole)

    def resizecols(self, index):
        '''Ajusta largura das colunas da tabela.'''
        if index.column() in self.cols_resized:
            self.resizeColumnToContents(index.column())

    def outputrows(self, toprow):
        '''Identifica linhas dentro do campo de visão da tabela.'''
        pass
        #TODO Está funcionando, só precisa ver se vale a pena usar...
        #bottomrow = self.verticalHeader().visualIndexAt(self.height())
        #rows = xrange(toprow, bottomrow)
        #for row in rows:
        #    index = self.model.index(row, 0, QModelIndex())
        #    filepath = self.model.data(index, Qt.DisplayRole)
        #    filepath = unicode(filepath.toString())
        #    self.emit(SIGNAL('visibleRow(filepath)'), filepath)

    def emitsaved(self):
        '''Emite aviso que os metadados foram gravados nos arquivos.'''
        self.emit(SIGNAL('savedToFile()'))

    def emitlost(self, filename):
        '''Emite aviso para remover entrada da lista de modificados.'''
        self.emit(SIGNAL('delEntry(filename)'), filename)

    def update_selection(self, selected, deselected):
        '''Pega a entrada selecionada, extrai os valores envia para editor.

        Os valores são enviados através de um sinal.
        '''
        #TODO Função obsoleta, ver se tem algo para aproveitar.
        deselectedindexes = deselected.indexes()
        if not deselectedindexes:
            selectedindexes = selected.indexes()
            self.selecteditems.append(selectedindexes)
        else:
            del self.selecteditems[:]
            selectedindexes = selected.indexes()
            self.selecteditems.append(selectedindexes)
        # Criando valores efetivamente da entrada selecionada.
        values = []
        for index in selectedindexes:
            value = self.model.data(index, Qt.DisplayRole)
            values.append((index, value.toString()))
        #self.emit(SIGNAL('thisIsCurrent(values)'), values)

    def changecurrent(self, current, previous):
        '''Identifica a célula selecionada, extrai valores e envia para editor.

        Os valores são enviados através de um sinal.
        '''
        values = []
        for col in xrange(self.ncols):
            index = self.model.index(current.row(), col, QModelIndex())
            value = self.model.data(index, Qt.DisplayRole)
            values.append((index, value.toString()))
        self.emit(SIGNAL('thisIsCurrent(values)'), values)


class TableModel(QAbstractTableModel):
    '''Modelo dos dados.'''
    def __init__(self, parent, mydata, header, *args):
        QAbstractTableModel.__init__(self, parent, *args)
        self.mydata = mydata
        self.header = header

    def rowCount(self, parent):
        '''Conta as linhas.'''
        return len(self.mydata)

    def columnCount(self, parent):
        '''Conta as colunas.'''
        if self.mydata:
            return len(self.mydata[0])
        else:
            return 0

    def data(self, index, role):
        '''Transforma dados brutos em elementos da tabela.'''
        if not index.isValid():
            return QVariant()
        elif role != Qt.DisplayRole and role != Qt.EditRole and \
                role != Qt.BackgroundRole:
            return QVariant()
        return QVariant(self.mydata[index.row()][index.column()])
        
    def headerData(self, col, orientation, role):
        '''Constrói cabeçalho da tabela.'''
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.header[col])
        return QVariant()

    def flags(self, index):
        '''Indicadores do estado de cada ítem.'''
        if not index.isValid():
            return Qt.ItemIsEnabled
        return QAbstractItemModel.flags(self, index) | Qt.ItemIsEditable

    def setData(self, index, value, role):
        '''Salva alterações nos dados a partir da edição da tabela.'''
        if index.isValid() and role == Qt.EditRole:
            oldvalue = self.mydata[index.row()][index.column()]
            if index.column() == 3:
                self.mydata[index.row()][index.column()] = unicode(
                        value.toString()).lower()
            else:
                self.mydata[index.row()][index.column()] = value.toString()
            self.emit(SIGNAL('dataChanged(index, value, oldvalue)'),
                    index, value, oldvalue)
            return True
        return False
    
    def sort(self, col, order):
        '''Ordena entradas a partir de valores de determinada coluna'''
        self.emit(SIGNAL('layoutAboutToBeChanged()'))
        self.mydata = sorted(self.mydata, key=operator.itemgetter(col))
        if order == Qt.DescendingOrder:
            self.mydata.reverse()
        self.emit(SIGNAL('layoutChanged()'))

    def setcolor(self, index, role):
        '''Pinta células da tabela.'''
        #FIXME Não funciona.
        print index, role
        if index.isValid() and role == Qt.BackgroundRole:
            return QVariant(QColor(Qt.yellow))

    def insert_rows(self, position, rows, parent, entry):
        '''Insere entrada na tabela.'''
        self.beginInsertRows(parent, position, position+rows-1)
        for row in xrange(rows):
            self.mydata.append(entry)
        self.endInsertRows()
        return True

    def remove_rows(self, position, rows, parent):
        '''Remove entrada da tabela.'''
        self.beginRemoveRows(parent, position, position+rows-1)
        for row in xrange(rows):
            self.mydata.pop(position)
        self.endRemoveRows()
        return True


class DockEditor(QWidget):
    '''Dock com campos para edição dos metadados.'''
    def __init__(self, parent):
        QWidget.__init__(self, parent)

        varnames = [
                ['title', 'caption', 'tags'],
                ['taxon', 'sp', 'source', 'author', 'rights'],
                ['size', 'location', 'city', 'state', 'country']
                ]
        labels = [
                [u'Título', u'Legenda', u'Marcadores'],
                [u'Táxon', u'Espécie', u'Especialista', u'Autor', u'Direitos'],
                [u'Tamanho', u'Local', u'Cidade', u'Estado', u'País']
                ]
        self.sizes = [
                '',
                '<0,1 mm',
                '0,1 - 1,0 mm',
                '1,0 - 10 mm',
                '10 - 100 mm',
                '>100 mm'
                ]

        self.changeStatus = parent.changeStatus

        self.tageditor = parent.tageditor
        self.tagcompleter = parent.tagcompleter

        self.hbox = QHBoxLayout()
        self.setLayout(self.hbox)

        e = 'Edit'

        for box in varnames:
            box_index = varnames.index(box)
            box_layid = 'form' + str(box_index)
            box_id = 'wid' + str(box_index)
            setattr(self, box_layid, QFormLayout())
            setattr(self, box_id, QWidget())
            for var in box:
                var_index = box.index(var)
                setattr(self, var, QLabel('&' + labels[box_index][var_index] + ':'))
                if var == 'caption':
                    setattr(self, var + e, QTextEdit())
                    self.captionEdit.setTabChangesFocus(True)
                elif var == 'size':
                    setattr(self, var + e, QComboBox())
                    eval('self.' + var + e + '.addItems(self.sizes)')
                elif var == 'tags':
                    setattr(self, var + e, self.tageditor)
                else:
                    setattr(self, var + e, QLineEdit())
                label = eval('self.' + var)
                edit = eval('self.' + var + e)
                label.setBuddy(edit)
                if box_index == 0:
                    self.form0.addRow(label, edit)
                elif box_index == 1:
                    self.form1.addRow(label, edit)
                elif box_index == 2:
                    self.form2.addRow(label, edit)
            eval('self.' + box_id + '.setLayout(self.' + box_layid + ')')
            self.hbox.addWidget(eval('self.' + box_id))

        # Inicia valores para o autocomplete
        self.autolistgen(parent.automodels)

        self.setMaximumHeight(180)

        self.connect(
                mainWidget,
                SIGNAL('thisIsCurrent(values)'),
                self.setcurrent
                )

        self.connect(
                mainWidget.model,
                SIGNAL('dataChanged(index, value, oldvalue)'),
                self.setsingle
                )

        self.connect(
                options,
                SIGNAL('rebuildcomplete(models)'),
                self.autolistgen
                )

    def autolistgen(self, models):
        '''Gera autocompletadores dos campos.'''
        self.tagcompleter.setWidget(self.tageditor)

        self.completer = MainCompleter(models.taxa, self)
        self.taxonEdit.setCompleter(self.completer)

        self.completer = MainCompleter(models.spp, self)
        self.spEdit.setCompleter(self.completer)

        self.completer = MainCompleter(models.sources, self)
        self.sourceEdit.setCompleter(self.completer)

        self.completer = MainCompleter(models.authors, self)
        self.authorEdit.setCompleter(self.completer)

        self.completer = MainCompleter(models.rights, self)
        self.rightsEdit.setCompleter(self.completer)

        self.completer = MainCompleter(models.locations, self)
        self.locationEdit.setCompleter(self.completer)

        self.completer = MainCompleter(models.cities, self)
        self.cityEdit.setCompleter(self.completer)

        self.completer = MainCompleter(models.states, self)
        self.stateEdit.setCompleter(self.completer)

        self.completer = MainCompleter(models.countries, self)
        self.countryEdit.setCompleter(self.completer)

    def setsingle(self, index, value, oldvalue):
        '''Atualiza campo de edição correspondente quando dado é alterado.'''
        #print index.row(), index.column(), unicode(value.toString()), unicode(oldvalue)
        if index.column() == 1:
            self.titleEdit.setText(value.toString())
        elif index.column() == 2:
            self.captionEdit.setText(value.toString())
        elif index.column() == 3:
            self.tagsEdit.setText(value.toString())
        elif index.column() == 4:
            self.taxonEdit.setText(value.toString())
        elif index.column() == 5:
            self.spEdit.setText(value.toString())
        elif index.column() == 6:
            self.sourceEdit.setText(value.toString())
        elif index.column() == 7:
            self.authorEdit.setText(value.toString())
        elif index.column() == 8:
            self.rightsEdit.setText(value.toString())
        elif index.column() == 9:
            for interval in self.sizes:
                if value.toString() == interval:
                    idx = self.sizes.index(interval)
                    self.sizeEdit.setCurrentIndex(idx)
                else:
                    pass
        elif index.column() == 10:
            self.locationEdit.setText(value.toString())
        elif index.column() == 11:
            self.cityEdit.setText(value.toString())
        elif index.column() == 12:
            self.stateEdit.setText(value.toString())
        elif index.column() == 13:
            self.countryEdit.setText(value.toString())

    def setcurrent(self, values):
        '''Atualiza campos de edição quando entrada é selecionada na tabela.'''
        if values:
            self.titleEdit.setText(values[1][1])
            self.captionEdit.setText(values[2][1])
            self.tagsEdit.setText(values[3][1])
            self.taxonEdit.setText(values[4][1])
            self.spEdit.setText(values[5][1])
            self.sourceEdit.setText(values[6][1])
            self.authorEdit.setText(values[7][1])
            self.rightsEdit.setText(values[8][1])
            for interval in self.sizes:
                if values[9][1] == interval:
                    idx = self.sizes.index(interval)
                    self.sizeEdit.setCurrentIndex(idx)
                else:
                    pass
            self.locationEdit.setText(values[10][1])
            self.cityEdit.setText(values[11][1])
            self.stateEdit.setText(values[12][1])
            self.countryEdit.setText(values[13][1])
            self.values = values

    def savedata(self):
        '''Salva valores dos campos para a tabela.'''
        #TODO Fundir com a função paste...
        indexes = mainWidget.selectedIndexes()
        rows = [index.row() for index in indexes]
        rows = list(set(rows))

        # Slices dos índices selecionados.
        nrows = len(rows)
        si = 0
        st = nrows
        
        # Título
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.titleEdit.text()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Legenda
        for index in indexes[si:st]:
            mainWidget.model.setData(index,
                    QVariant(self.captionEdit.toPlainText()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Marcadores
        for index in indexes[si:st]:
            mainWidget.model.setData(index,
                    QVariant(unicode(self.tagsEdit.text()).lower()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Táxon
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.taxonEdit.text()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Espécie
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.spEdit.text()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Especialista
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.sourceEdit.text()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Autor
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.authorEdit.text()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Direitos
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.rightsEdit.text()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Tamanho
        for index in indexes[si:st]:
            mainWidget.model.setData(index,
                    QVariant(self.sizeEdit.currentText()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Local
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.locationEdit.text()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Cidade
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.cityEdit.text()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Estado
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.stateEdit.text()),
                    Qt.EditRole)
        si = st
        st = si + nrows 

        # Estado
        for index in indexes[si:st]:
            mainWidget.model.setData(index, QVariant(self.countryEdit.text()),
                    Qt.EditRole)

        mainWidget.setFocus(Qt.OtherFocusReason)
        self.changeStatus(u'%d entradas alteradas!' % nrows, 5000)


class AutoModels():
    '''Cria modelos para autocompletar campos de edição.'''
    def __init__(self, list):
        self.autolists = list
        for k, v in self.autolists.iteritems():
            if v:
                v.sort()
                setattr(self, k, QStringListModel(v))
            else:
                setattr(self, k, QStringListModel())


class MainCompleter(QCompleter):
    '''Autocomplete principal.'''
    def __init__(self, model, parent):
        QCompleter.__init__(self, model, parent)

        self.setModel(model)
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.setModelSorting(QCompleter.CaseInsensitivelySortedModel)


class TagCompleter(QCompleter):
    '''Completador de marcadores.

    Adaptado de John Schember:
    john.nachtimwald.com/2009/07/04/qcompleter-and-comma-separated-tags/    
    '''
    def __init__(self, model, parent):
        QCompleter.__init__(self, model, parent)
        self.model = model

    def update(self, text_tags, completion_prefix):
        #tags = self.list.difference(text_tags)
        #model = QStringListModel(tags, self)
        self.setModel(self.model)

        self.setCompletionPrefix(completion_prefix)
        if completion_prefix.strip() != '':
            self.complete()


class CompleterLineEdit(QLineEdit):
    '''Editor especial para marcadores.

    Adaptado de John Schember:
    john.nachtimwald.com/2009/07/04/qcompleter-and-comma-separated-tags/
    '''
    def __init__(self, *args):
        QLineEdit.__init__(self)

        self.connect(self, SIGNAL('textChanged(QString)'), self.text_changed)

    def text_changed(self, text):
        all_text = unicode(text)
        text = all_text[:self.cursorPosition()]
        prefix = text.split(',')[-1].strip()

        text_tags = []
        for t in all_text.split(','):
            t1 = unicode(t).strip()
            if t1 != '':
                text_tags.append(t)
        text_tags = list(set(text_tags))

        self.emit(SIGNAL('text_changed(PyQt_PyObject, PyQt_PyObject)'),
            text_tags, prefix)

    def complete_text(self, text):
        cursor_pos = self.cursorPosition()
        before_text = unicode(self.text())[:cursor_pos]
        after_text = unicode(self.text())[cursor_pos:]
        prefix_len = len(before_text.split(',')[-1].strip())
        self.setText('%s%s, %s' % (before_text[:cursor_pos - prefix_len], text,
            after_text))
        self.setCursorPosition(cursor_pos - prefix_len + len(text) + 2)


class DockGeo(QWidget):
    '''Dock para editar a geolocalização da imagem.'''
    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.changeStatus = parent.changeStatus

        # Layout do dock
        self.hbox = QHBoxLayout()
        
        # Editor
        self.lat_label = QLabel(u'Latitude:')
        self.lat = QLineEdit()
        self.long_label = QLabel(u'Longitude:')
        self.long = QLineEdit()
        self.updatebutton = QPushButton(u'&Atualizar', self)
        self.savebutton = QPushButton(u'&Gravar', self)

        # Layout do Editor
        self.editbox = QFormLayout()
        self.editbox.addRow(self.lat_label, self.lat)
        self.editbox.addRow(self.long_label, self.long)
        self.editbox.addRow(self.updatebutton)
        self.editbox.addRow(self.savebutton)

        # Widgets do Dock
        self.geolocation = QWidget()
        self.geolocation.setLayout(self.editbox)
        self.map = QWebView(self)

        # Tamanhos
        self.geolocation.setFixedWidth(200)
        self.map.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # Layout do Dock
        self.hbox.addWidget(self.geolocation)
        self.hbox.addWidget(self.map)
        self.setLayout(self.hbox)

        self.connect(
                self.savebutton,
                SIGNAL('clicked()'),
                self.write_geo
                )

        self.connect(
                self.updatebutton,
                SIGNAL('clicked()'),
                self.update_geo
                )

        self.connect(
                mainWidget,
                SIGNAL('thisIsCurrent(values)'),
                self.setcurrent
                )

        self.connect(
                parent,
                SIGNAL('ismapSelected(visible)'),
                self.state
                )

    def state(self, visible):
        '''Relata se aba está visível e/ou selecionada.

        Captura sinal emitido pelo mainWidget.
        
        Por não distinguir entre visível e aba selecionada não funciona em
        algumas situações.
        '''
        #TODO Tem alguma alternativa para descobrir se a aba está selecionada?
        self.ismap_selected = visible
        try:
            if visible:
                # Se estiver visível, carregar o mapa.
                self.load_geocode(self.gps)
        except:
            pass

    def setdms(self, dms):
        '''Atualiza as coordenadas do editor.'''
        self.lat.setText(u'%s %d°%d\'%d"' % (
            dms['latref'], dms['latdeg'], dms['latmin'], dms['latsec']))
        self.long.setText(u'%s %d°%d\'%d"' % (
            dms['longref'], dms['longdeg'], dms['longmin'], dms['longsec']))

    def update_geo(self):
        '''Captura as coordenadas do marcador para atualizar o editor.'''
        # Captura coordenadas do último marcador do mapa.
        mark = self.map.page().mainFrame().evaluateJavaScript(
                'document.getElementById("markerlocation").value').toString()
        # Transforma a string em lista com floats, limpando os parenteses.
        marker = str(mark).strip('()').split(', ')
        decimals = [float(c) for c in marker]
        # Converte decimal para sistema de coordenadas
        dms = self.un_decimal(decimals[0], decimals[1])
        self.setdms(dms)

    def un_decimal(self, lat, long):
        '''Converte o valor decimal das coordenadas.
        
        Retorna dicionário com referência cardinal, graus, minutos e segundos.
        '''
        # Latitude
        latdeg = int(abs(lat))
        latmin = (abs(lat) - latdeg) * 60
        latsec = int((latmin - int(latmin)) * 60)
        latmin = int(latmin)

        # Longitude
        longdeg = int(abs(long))
        longmin = (abs(long) - longdeg) * 60
        longsec = int((longmin - int(longmin)) * 60)
        longmin = int(longmin)

        # Cardinals
        if lat < 0:
            latref = 'S'
        else:
            latref = 'N'
        if long < 0:
            longref = 'W'
        else:
            longref = 'E'

        dms = {
                'latref': latref,
                'latdeg': latdeg,
                'latmin': latmin,
                'latsec': latsec,
                'longref': longref,
                'longdeg': longdeg,
                'longmin': longmin,
                'longsec': longsec,
                }

        return dms

    def write_html(self, unset=0, lat=0.0, long=0.0, zoom=5):
        '''Carrega código HTML da QWebView com mapa do Google Maps.

        Usando o API V3.
        '''
        self.map.setHtml('''
        <html>
        <head>
        <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
        <meta http-equiv="content-type" content="text/html; charset=UTF-8"/>
        <title>Véliger</title>
        <script type="text/javascript" src="http://maps.google.com/maps/api/js?sensor=false&language=pt-BR"></script>
        <script type="text/javascript">
            var map;
            var marker;
            function initialize() {
                var unset = %d;
                var local = new google.maps.LatLng(%f,%f);
                var myOptions = {
                    zoom: %d,
                    center: local,
                    mapTypeId: google.maps.MapTypeId.ROADMAP
                }

                map = new google.maps.Map(document.getElementById("map_canvas"), myOptions);
                    
                if (unset == 0) {
                    var marker = new google.maps.Marker({
                        position: local,
                        map: map,
                        title:"Local",
                        draggable: true,
                    });
                    document.getElementById("markerlocation").value = marker.position;
                }
                else {
                    google.maps.event.addListener(map, 'rightclick', function(event) {
                        placeMarker(event.latLng);
                    });
                }

                google.maps.event.addListener(marker, 'dragend', function() {
                    document.getElementById("markerlocation").value = marker.position;
                    map.setCenter(marker.position);
                });
            }
            
            function placeMarker(location) {
                var clickedLocation = new google.maps.LatLng(location);

                var marker = new google.maps.Marker({
                    position: location,
                    map: map,
                    draggable: true,
                });
                
                document.getElementById("markerlocation").value = marker.position;

                map.setCenter(location);
                map.setZoom(5);

                google.maps.event.addListener(marker, 'dragend', function() {
                    document.getElementById("markerlocation").value = marker.position;
                    map.setCenter(marker.position);
                });

            }

        </script>
        </head>
        <body style="margin:0px; padding:0px;" onload="initialize()">
            <div id="map_canvas" style="width: 100%%; height: 100%%;"></div>
            <input id="markerlocation" type="hidden" />
        </body>
        </html>
        ''' % (unset, lat, long, zoom))

    def load_geocode(self, gps):
        '''Pega coordenadas e chama mapa com as variáveis correspondetes.'''
        if gps:
            # Cria valores decimais das coordenadas
            self.lat_dec = self.get_decimal(
                    self.gps['latref'], self.gps['latdeg'],
                    self.gps['latmin'], self.gps['latsec'])
            self.long_dec = self.get_decimal(
                    self.gps['longref'], self.gps['longdeg'],
                    self.gps['longmin'], self.gps['longsec'])
            self.write_html(lat=self.lat_dec, long=self.long_dec)
        else:
            # Imagem sem coordenadas
            self.write_html(unset=1, zoom=1)

    def get_exif(self, filepath):
        '''Extrai o exif da imagem selecionada usando o pyexiv2 0.2.2.'''
        exif_meta = pyexiv2.ImageMetadata(unicode(filepath))
        exif_meta.read()
        gps = {}
        try:
            gps['latref'] = exif_meta['Exif.GPSInfo.GPSLatitudeRef'].value
            gps['latdeg'] = self.resolve(exif_meta['Exif.GPSInfo.GPSLatitude'].value[0])
            gps['latmin'] = self.resolve(exif_meta['Exif.GPSInfo.GPSLatitude'].value[1])
            gps['latsec'] = self.resolve(exif_meta['Exif.GPSInfo.GPSLatitude'].value[2])
            gps['longref'] = exif_meta['Exif.GPSInfo.GPSLongitudeRef'].value
            gps['longdeg'] = self.resolve(exif_meta['Exif.GPSInfo.GPSLongitude'].value[0])
            gps['longmin'] = self.resolve(exif_meta['Exif.GPSInfo.GPSLongitude'].value[1])
            gps['longsec'] = self.resolve(exif_meta['Exif.GPSInfo.GPSLongitude'].value[2])
            return gps
        except:
            return gps

    def resolve(self, frac):
        '''Resolve a fração das coordenadas para int.

        Por padrão os valores do exif são guardados como frações. Por isso é
        necessário converter.
        '''
        fraclist = str(frac).split('/')
        result = int(fraclist[0]) / int(fraclist[1])
        return result

    def setcurrent(self, values):
        '''Mostra geolocalização da imagem selecionada.'''
        if values and values[0][1] != '':
            self.current_filepath = values[0][1]
            # Extrai metadados da imagem (exif).
            self.gps = self.get_exif(self.current_filepath)
            # Atualiza o editor com novos valores.
            if self.gps:
                self.setdms(self.gps)
                self.savebutton.setEnabled(True)
            else:
                self.lat.clear()
                self.long.clear()
            # Se o dock estiver visível, carregar o mapa.
            if self.ismap_selected:
                self.load_geocode(self.gps)
            else:
                # Possivelmente isso não vai aparecer nunca por causa do
                # self.state.
                self.map.setHtml('''<html><head></head><body><h1>Recarregue</h1></body></html>''')

    def get_decimal(self, ref, deg, min, sec):
        '''Descobre o valor decimal das coordenadas.'''
        decimal_min = (min * 60.0 + sec) / 60.0
        decimal = (deg * 60.0 + decimal_min) / 60.0
        negs = ['S', 'W']
        if ref in negs:
            decimal = -decimal
        return decimal

    def write_geo(self):
        '''Grava novas coordenadas nas imagens selecionadas.'''
        # Pega imagens selecionadas.
        indexes = mainWidget.selectionModel.selectedRows()
        if indexes:
            filepaths = []
            indexes = [index.row() for index in indexes]
            # Pega o nome dos arquivos.
            for row in indexes:
                index = mainWidget.model.index(row, 0, QModelIndex())
                filepath = mainWidget.model.data(index, Qt.DisplayRole)
                filepaths.append(filepath.toString())
            # Criar instância para poder gravar metadados.
            for filepath in filepaths:
                image = pyexiv2.ImageMetadata(unicode(filepath))
                image.read()
                newlat, newlong = self.newgps()
                if newlat and newlong:
                    self.changeStatus(u'Gravando novas coordenadas de %s...' %
                            filepath)
                    image['Exif.GPSInfo.GPSLatitudeRef'] = str(newlat['ref'])
                    image['Exif.GPSInfo.GPSLatitude'] = (
                            newlat['deg'], newlat['min'], newlat['sec'])
                    image['Exif.GPSInfo.GPSLongitudeRef'] = str(newlong['ref'])
                    image['Exif.GPSInfo.GPSLongitude'] = (
                            newlong['deg'], newlong['min'], newlong['sec'])
                    image.write()
                    self.changeStatus(
                            u'Gravando novas coordenadas de %s... pronto!'
                            % filepath, 5000)
                else:
                    self.changeStatus(
                            u'Deletando o campo Exif.GPSInfo de %s...' %
                            filepath)
                    image.__delitem__('Exif.GPSInfo.GPSLatitudeRef')
                    image.__delitem__('Exif.GPSInfo.GPSLatitude')
                    image.__delitem__('Exif.GPSInfo.GPSLongitudeRef')
                    image.__delitem__('Exif.GPSInfo.GPSLongitude')
                    image.write()
                    self.changeStatus(
                            u'Deletando o campo Exif.GPSInfo de %s... pronto!'
                            % filepath, 5000)

            #XXX Aqui o mapa é atualizado de acordo com as novas coordenadas.
            if newlat and newlong:
                lat_dec = self.get_decimal(
                        newlat['ref'], self.resolve(newlat['deg']),
                        self.resolve(newlat['min']), self.resolve(newlat['sec']))
                long_dec = self.get_decimal(
                        newlat['ref'], self.resolve(newlong['deg']),
                        self.resolve(newlong['min']), self.resolve(newlong['sec']))

                self.write_html(lat=lat_dec, long=long_dec)
            else:
                self.lat.clear()
                self.long.clear()
                self.write_html(unset=1, zoom=1)

            self.changeStatus(u'%d imagens alteradas!' % len(filepaths), 5000)
        else:
            self.changeStatus(u'Nenhuma imagem selecionada!' % len(filepaths), 5000)

    def newgps(self):
        '''Pega as novas coordenadas do editor.'''
        lat = self.lat.text()
        long = self.long.text()
        # Se um dos campos estiver vazio, deletar geolocalização.
        if not lat or not long:
            newlat, newlong = {}, {}
        else:
            newlat = self.geodict(lat)
            newlong = self.geodict(long)
        return newlat, newlong

    def geodict(self, string):
        '''Extrai coordenadas da string do editor.'''
        # Utiliza expressões regulares.
        geo = re.findall('\w+', string)
        gps = {
                'ref': geo[0],
                'deg': pyexiv2.utils.Rational(geo[1], 1),
                'min': pyexiv2.utils.Rational(geo[2], 1),
                'sec': pyexiv2.utils.Rational(geo[3], 1),
                }
        return gps


class DockThumb(QWidget):
    '''Dock para mostrar o thumbnail da imagem selecionada.'''
    def __init__(self):
        QWidget.__init__(self)

        self.setMaximumWidth(400)
        self.vbox = QVBoxLayout()
        self.pic = QPixmap()
        self.thumb = QLabel()
        self.name = QLabel()
        self.timestamp = QLabel()

        self.thumb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.thumb.setMaximumWidth(400)
        self.thumb.setMinimumSize(100, 100)
        self.thumb.setAlignment(Qt.AlignHCenter)

        self.vbox.addWidget(self.thumb)
        self.vbox.addWidget(self.name)
        self.vbox.addWidget(self.timestamp)
        self.vbox.addStretch(1)

        self.name.setWordWrap(True)
        self.setLayout(self.vbox)

        QPixmapCache.setCacheLimit(81920)

        self.connect(
                mainWidget,
                SIGNAL('thisIsCurrent(values)'),
                self.setcurrent
                )

        self.connect(
                mainWidget,
                SIGNAL('visibleRow(filepath)'),
                self.pixmapcache
                )

    def pixmapcache(self, filepath):
        '''Cria cache para thumbnail.'''
        filename = os.path.basename(unicode(filepath))
        thumbpath = os.path.join(thumbdir, filename)
        # Tenta abrir o cache
        if not QPixmapCache.find(filename, self.pic):
            self.pic.load(thumbpath)
            #print 'Criando cache da imagem %s...' % filename,
            QPixmapCache.insert(filename, self.pic)
            #print 'pronto!'
        else:
            pass
        return self.pic
    
    def setcurrent(self, values):
        '''Mostra thumbnail, nome e data de modificação da imagem.

        Captura sinal com valores, tenta achar imagem no cache e exibe
        informações.
        '''
        if values and values[0][1] != '':
            filename = os.path.basename(unicode(values[0][1]))
            self.name.setText(unicode(filename))
            timestamp = values[14][1]
            self.timestamp.setText(timestamp)

            # Tenta abrir o cache
            self.pic = self.pixmapcache(values[0][1])
        elif values and values[0][1] == '':
            self.pic = QPixmap()
            self.name.clear()
            self.timestamp.clear()
            self.thumb.clear()
        else:
            self.pic = QPixmap()
            self.name.clear()
            self.timestamp.clear()
            self.thumb.clear()
        self.updateThumb()

    def updateThumb(self):
        '''Atualiza thumbnail.'''
        if self.pic.isNull():
            self.thumb.setText(u'Imagem indisponível')
            pass
        else:
            scaledpic = self.pic.scaled(self.width(),
                    self.height()-65,
                    Qt.KeepAspectRatio, Qt.FastTransformation)
            self.thumb.setPixmap(scaledpic)

    def resizeEvent(self, event):
        '''Lida com redimensionamento do thumbnail.'''
        event.accept()
        self.updateThumb()


class DockUnsaved(QWidget):
    '''Exibe lista com imagens modificadas.

    Utiliza dados do modelo em lista. Qualquer imagem modificada será
    adicionada à lista. Seleção na lista seleciona entrada na tabela. Gravar
    salva metadados de cada ítem da lista nas respectivas imagens.
    '''
    def __init__(self):
        QWidget.__init__(self)

        self.mylist = updatelist
        self.model = ListModel(self, self.mylist)

        self.view = QListView()
        self.view.setModel(self.model)
        self.view.selectionModel = self.view.selectionModel()
        self.view.setAlternatingRowColors(True)

        self.clearselection = QAction('Limpar seleção', self)
        self.clearselection.setShortcut('Esc')
        self.clear = lambda: self.view.selectionModel.clearSelection()
        self.clearselection.triggered.connect(self.clear)
        self.addAction(self.clearselection)

        self.savebutton = QPushButton(u'&Gravar', self)
        if not self.model.mylist:
            self.savebutton.setDisabled(True)

        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.view)
        self.vbox.addWidget(self.savebutton)
        self.setLayout(self.vbox)

        self.connect(
                mainWidget.model,
                SIGNAL('dataChanged(index, value, oldvalue)'),
                self.insertentry
                )

        self.connect(
                self.view.selectionModel,
                SIGNAL('selectionChanged(QItemSelection, QItemSelection)'),
                self.sync_setselection
                )

        self.connect(
                self.savebutton,
                SIGNAL('clicked()'),
                self.writeselected
                )

        self.connect(
                mainWidget,
                SIGNAL('savedToFile()'),
                self.clearlist
                )

        self.connect(
                mainWidget,
                SIGNAL('delEntry(filename)'),
                self.delentry
                )

    def sync_setselection(self, selected, deselected):
        '''Sincroniza seleção da tabela com a seleção da lista.'''
        indexes = selected.indexes()
        if indexes:
            index = indexes[0]
            filename = self.model.data(index, Qt.DisplayRole)
            filename = filename.toString()
            self.emit(SIGNAL('syncSelection(filename)'), filename)

    def writeselected(self):
        '''Emite sinal para gravar metadados na imagem.'''
        self.emit(SIGNAL('commitMeta(entries)'), self.mylist)

    def insertentry(self, index, value, oldvalue):
        '''Insere entrada na lista.
        
        Checa se a modificação não foi nula (valor atual == valor anterior) e
        se a entrada é duplicada.
        '''
        if value == oldvalue:
            pass
        else:
            index = mainWidget.model.index(index.row(), 0, QModelIndex())
            filepath = mainWidget.model.data(index, Qt.DisplayRole)
            filename = os.path.basename(unicode(filepath.toString()))
            matches = self.matchfinder(filename)
            if len(matches) == 0:
                self.model.insert_rows(0, 1, QModelIndex(), filename)
                self.savebutton.setEnabled(True)
            else:
                pass

    def delentry(self, filename):
        '''Remove entrada da lista.'''
        matches = self.matchfinder(filename)
        if len(matches) == 1:
            match = matches[0]
            self.model.remove_rows(match.row(), 1, QModelIndex())
            if not self.model.mylist:
                self.savebutton.setDisabled(True)

    def clearlist(self):
        '''Remove todas as entradas da lista.'''
        rows = self.model.rowCount(self.model)
        if rows > 0:
            self.model.remove_rows(0, rows, QModelIndex())
            self.savebutton.setDisabled(True)
        else:
            print 'Nada pra deletar.'

    def matchfinder(self, candidate):
        '''Buscador de duplicatas.'''
        index = self.model.index(0, 0, QModelIndex())
        matches = self.model.match(index, 0, candidate, -1, Qt.MatchExactly)
        return matches

    def resizeEvent(self, event):
        '''Lida com redimensionamentos.'''
        event.accept()


class ListModel(QAbstractListModel):
    '''Modelo com lista de imagens modificadas.'''
    def __init__(self, parent, list, *args):
        QAbstractListModel.__init__(self, parent, *args)
        self.mylist = list

    def rowCount(self, parent):
        '''Conta linhas.'''
        return len(self.mylist)

    def data(self, index, role):
        '''Cria elementos da lista a partir dos dados.'''
        if not index.isValid():
            return QVariant()
        elif role != Qt.DisplayRole:
            return QVariant()
        return QVariant(self.mylist[index.row()])

    def insert_rows(self, position, rows, parent, entry):
        '''Insere linhas.'''
        self.beginInsertRows(parent, position, position+rows-1)
        for row in xrange(rows):
            self.mylist.append(entry)
        self.endInsertRows()
        return True

    def remove_rows(self, position, rows, parent):
        '''Remove linhas.'''
        self.beginRemoveRows(parent, position, position+rows-1)
        for row in xrange(rows):
            self.mylist.pop(position)
        self.endRemoveRows()
        return True


class FlushFile(object):
    '''Tira o buffer do print.

    Assim rola juntar prints diferentes na mesma linha. Só pra ficar
    bonitinho... meio inútil.
    '''
    def __init__(self, f):
        self.f = f
    def write(self, x):
        self.f.write(x)
        self.f.flush()


#=== MAIN ===#


class InitPs():
    '''Inicia variáveis e parâmetros globais do programa.'''
    def __init__(self):
        global tablepickle
        global listpickle
        global autopickle
        global header
        global datalist
        global updatelist
        global autolists
        global thumbdir

        thumbdir = 'thumbs'

        # Redefine o stdout para ser flushed após print
        #sys.stdout = FlushFile(sys.stdout)
        
        # Cabeçalho horizontal da tabela principal
        header = [
                u'Arquivo', u'Título', u'Legenda', u'Marcadores',
                u'Táxon', u'Espécie', u'Especialista', u'Autor', u'Direitos',
                u'Tamanho', u'Local', u'Cidade', u'Estado', u'País',
                u'Timestamp'
                ]
        
        # Nome do arquivo Pickle para tabela
        tablepickle = 'tablecache'
        try:
            tablecache = open(tablepickle, 'rb')
            datalist = pickle.load(tablecache)
            tablecache.close()
            if not datalist:
                datalist.append([
                    u'', u'', u'', u'', u'',
                    u'', u'', u'', u'', u'',
                    u'', u'', u'', u'', u'',
                    ])
        except:
            f = open(tablepickle, 'wb')
            f.close()
            datalist = [[
                u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'',
                ],]
        # Nome do arquivo Pickle para lista
        listpickle = 'listcache'
        try:
            listcache = open(listpickle, 'rb')
            updatelist = pickle.load(listcache)
            listcache.close()
        except:
            f = open(listpickle, 'wb')
            f.close()
            updatelist = []

        # Nome do arquivo Pickle para autocomplete
        autopickle = 'autocomplete'
        try:
            autocomplete = open(autopickle, 'rb')
            autolists = pickle.load(autocomplete)
            autocomplete.close()
        except:
            f = open(autopickle, 'wb')
            autolists = {
                    'tags': [],
                    'taxa': [],
                    'spp': [],
                    'sources': [],
                    'authors': [],
                    'rights': [],
                    'locations': [],
                    'cities': [],
                    'states': [],
                    'countries': [],
                    }
            pickle.dump(autolists, f)                    
            f.close()

if __name__ == '__main__':
    initps = InitPs()
    app = QApplication(sys.argv)
    app.setOrganizationName(u'CEBIMar-USP')
    app.setOrganizationDomain(u'www.usp.br/cbm')
    app.setApplicationName(u'VÉLIGER')
    main = MainWindow()

    main.show()
    sys.exit(app.exec_())
