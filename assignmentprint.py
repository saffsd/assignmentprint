"""
Utility funtions and classes for preparing project marking bundles
for student assignments.

Marco Lui <saffsd@gmail.com>, November 2012
"""
import os, sys, csv, re
import tokenize, textwrap, token
import trace, threading
import imp
import contextlib

from cStringIO import StringIO
from pprint import pformat

import pep8
from collections import Sequence, Mapping, Sized

RE_FILENAME = re.compile(r'proj2-(?P<filename>\w+).py')
RE_DIRNAME = re.compile(r'proj2-(?P<dirname>\w+)')

def as_module(path, name='submitted'):
  module = imp.new_module(name)
  with open(path) as f:
    try:
        # suppress stdout
        sys.stdout = mystdout = StringIO()
        exec f in module.__dict__

    except Exception, e:
        raise ImportError, "import failed: '{0}'".format(e)
    finally:
        sys.stdout = sys.__stdout__
  return module, mystdout.getvalue()


def item2strs(item, max_lines=None):
  output = pformat(item)
  if max_lines is None or len(output.splitlines()) <= max_lines:
    retval = output.splitlines()
  else:
    if isinstance(item, Mapping):
      itemlen = len(item)
      retval = ["<{0} of len {1}>".format(type(item),itemlen)]
      for i in item.items()[:max_lines-2]:
        retval.append(str(i))
      retval.append(['... ({0} more items)'.format(itemlen-max_lines+2)])
    elif isinstance(item, Sequence):
      itemlen = len(item)
      retval = ["<{0} of len {1}>".format(type(item),itemlen)]
      for i in item[:max_lines-2]:
        retval.append(str(i))
      retval.append(['... ({0} more items)'.format(itemlen-max_lines+2)])
    else:
      retval = ["<item with repr len {0}>".format(len(repr(item)))]
  
  # Add the item type to the start
  retval[0] = "({0}) {1}".format(type(item), retval[0])
  return retval

def split_comments(line):
  code = []
  noncode = []
  try:
    for tk in tokenize.generate_tokens(StringIO(line).readline):
      if tk[2][0] != 1:
        break
      if tk[0] == tokenize.COMMENT:
        noncode.append(tk[:2])
      else:
        code.append(tk)
  except tokenize.TokenError:
    pass

  retval = tokenize.untokenize(code).strip(), tokenize.untokenize(noncode).strip()
  #retval = ''.join(c[1] for c in code), ''.join(c[1] for c in noncode)
  return retval

def get_indent(code):
  tokens = tokenize.generate_tokens(StringIO(code).readline)
  tk = tokens.next()
  indent = tk[1] if tk[0] == token.INDENT else ''
  return indent

def wrap_comment(line, width, add_indent=2):
  """
  This assumes that line contains a (potentially whitespace-indented)
  comment, and no actual code. It will assume anything before the
  comment marker is padding, and will maintain the indent level 
  thereof.
  """
  code, comm = split_comments(line)

  indent = get_indent(line)
  if len(indent) > width/2:
    # Comment starts really far right, we shift it 
    # to start quarter way through the width
    indent = ' ' * width/4
  retval = textwrap.wrap(comm, width, 
                          initial_indent= indent,
                          subsequent_indent= indent + '#' + ' '*add_indent,
                        )
  return retval


def wrap_code(code, width, add_indent ='  '):
  """
  Attempts to wrap a single line of code, respecting token
  boundaries.
  """
  tokens = tokenize.generate_tokens(StringIO(code).readline)
  indent = get_indent(code)

  chunk_width = width - len(indent)
  chunk_start = 0
  chunk_end = 0
  chunks = []
  first_chunk = True
  try:
    for tk_type, tk_text, tk_start, tk_end, _ in tokens:
      if tk_start[0] != tk_end[0]:
        raise ValueError, "token spanning multiple lines"
      tk_len = tk_end[1] - tk_start[1]

      if first_chunk:
        chunk_indent = '' # the indent is part of the tokens
      else:
        chunk_indent = indent + add_indent

      chunk_width = width - len(chunk_indent)
      
      if tk_end[1]-chunk_start >= chunk_width:
        # this token starts a new chunk
        chunk = chunk_indent+code[chunk_start:chunk_end]+'\\'
        assert len(chunk) <= width
        chunks.append(chunk)
        chunk_start = tk_start[1]
        first_chunk = False
      chunk_end = tk_end[1]
      assert len(chunk_indent+code[chunk_start:chunk_end]+'\\') <= width
  except tokenize.TokenError:
    # unmatched somethingorother, we don't really care as it 
    # may be matched on another line
    pass
  finally:
    # flush remaining chunk
    rest = code[chunk_start:]
    if len(rest) == 1:
      # if the token is only 1 character, it can replace the line continuation
      chunks[-1] = chunks[-1][:-1] + rest
    else:
      chunk = chunk_indent + rest
      assert len(chunk) <= width
      chunks.append(chunk)

  return chunks


def wrap_line(line, width):
  """
  Attempt to intelligently wrap Python code to width
  This also moves any comments to a line prior.
  """
  if len(line) <= width:
    # shortcut if the line is shorter than the width required
    return [line]

  _line = line.lstrip()
  indent = len(line) - len(_line)
  code, comm = split_comments(_line)

  if code:
    # there are comments, we output these first
    if comm:
      c = ' ' * indent + comm
      retval = wrap_comment(c, width)
    else:
      retval = []
    
    c = ' ' * indent + code
    retval.extend(wrap_code(c, width))

    return retval

  elif comm:
    # This line only contains comments. Wrap accordingly.
    return wrap_comment(line, width)
  
  else:
    return ['']


def find_submission(path):
  """
  Tries to find a submission in a given path.
  Returns username, submission_path, else None
  """
  if os.path.isdir(path):
    m = RE_DIRNAME.search(path)
    if m is not None:
      dir_items = set(os.listdir(path))
      username = m.group('dirname')
      submission_name = username + '.py'
      if submission_name in dir_items:
        item_path = os.path.join(path, submission_name)
        return username, item_path

  elif os.path.isfile(path):
    m = RE_FILENAME.search(path)
    if m is not None:
      username = m.group('filename')
      return username, path

# from http://code.activestate.com/recipes/534166-redirectedio-context-manager-and-redirect_io-decor/
class RedirectedIO(object):
    def __init__(self, target=None, mode='a+',
                 close_target=True):
        try:
            target = open(target, mode)
        except TypeError:
            if target is None:
                target = StringIO()
        self.target = target
        self.close_target = close_target

    def __enter__(self):
        """ Redirect IO to self.target.
        """
        self.original_stdout = sys.stdout
        sys.stdout = self.target
        return self.target

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ Restore stdio and close the file.
        """
        sys.stdout = self.original_stdout
        if self.close_target:
            self.target.close()

class ProjectPrinter(object):
  """
  This class wraps a file-like object and provides
  a series of methods for doing relevant output to
  it.
  """
  def __init__(self, target, pagewidth):
    self.target = target
    self.pagewidth = pagewidth

  def writeln(self, line='', wrap=False):
    if wrap:
      self.target.write(textwrap.fill(line, width=self.pagewidth) + '\n')
    else:
      for l in line.splitlines():
        self.target.write(textwrap.fill(l, width=self.pagewidth) + '\n')

  def cwriteln(self, line):
    """
    Write a centered line
    """
    self.writeln("{0:^{1}}".format(line, self.pagewidth))

  def hr(self, symbol='#'):
    if len(symbol) != 1:
      raise ValueError, "symbol must be a single character"
    self.writeln(symbol * self.pagewidth)


  def boxed_text(self, text, symbol='+', boxwidth=None, align='c', wrap=False):
    if boxwidth is None:
      boxwidth = self.pagewidth
    if boxwidth < 0:
      boxwidth = self.pagewidth + boxwidth
    if self.pagewidth < boxwidth:
      raise ValueError, "box wider than page"
    if len(symbol) != 1:
      raise ValueError, "symbol must be a single character"

    if isinstance(text, basestring):
      if wrap:
        lines = textwrap.wrap(text, width=boxwidth-2*(len(symbol)+1))
      else:
        lines = text.splitlines()
    else:
      lines = text 


    self.cwriteln(symbol * boxwidth)
    for line in lines:
      if len(line) > boxwidth-2*(len(symbol)+1):
        # line too long!
        _lines = textwrap.wrap(line, width=boxwidth-2*(len(symbol)+1), subsequent_indent = '  ')
      else:
        _lines = [line]
      for _line in _lines:
        if align == 'c':
          self.cwriteln('{0}{1:^{2}}{0}'.format(symbol, _line, boxwidth-2))
        elif align == 'r':
          self.cwriteln('{0}{1:>{2}} {0}'.format(symbol, _line, boxwidth-3))
        else:
          self.cwriteln('{0} {1:<{2}}{0}'.format(symbol, _line, boxwidth-3))
    self.cwriteln(symbol * boxwidth)

  def display_code(self, path):
    """
    Display code with intelligent wrapping
    """
    with open(path) as f:
      for i, line in enumerate(f):
        if len(line) > self.pagewidth - 6:
          # Line too wide. Need to cleverly wrap it.
          
          #_line = line.lstrip()
          #indent = len(line) - len(_line)
          indent = get_indent(line)
          code, comm = split_comments(line)

          if code:
            if comm:
              for l in wrap_comment(line, self.pagewidth-6):
                self.writeln('      {0}'.format(l))

            clines = wrap_code(indent + code, self.pagewidth - 6)
            self.writeln('{0:>4}* {1}'.format(i+1, clines[0]))
            for l in clines[1:]:
              self.writeln('      {0}'.format(l))
          else:
            # only comments on this line
            c_wrap = wrap_comment(line, self.pagewidth-6)
            if c_wrap:
              self.writeln( '{0:>4}: {1}'.format(i+1, c_wrap[0]) )
              for l in c_wrap[1:]:
                self.writeln('      {0}'.format(l))
            
                
          """
          # We splice out comments
          try:
            tokens = list(tokenize.generate_tokens(StringIO(line).readline))
            comments = ''.join(t[1] for t in tokens if t[0] == tokenize.COMMENT)
            noncomments = [ (t[0],t[1]) for t in tokens if t[0] != tokenize.COMMENT ]
            ncline = tokenize.untokenize(noncomments).rstrip()
          except tokenize.TokenError:
            # This happens with unmatched things - in particular triplequote
            # we just pretend the line had no comments in this case
            comments = ''
            ncline = line

          if ncline.lstrip():
            # More than comments on this line
            # Write the comments first, followed by the code
            if comments.strip():
              lead_gap = len(ncline) - len(ncline.lstrip())
              comments = ' '*lead_gap + comments
              c_wrap = wrap_comment(comments, self.pagewidth-6)
              self.writeln('      {0}'.format(c_wrap[0]))
              for l in c_wrap[1:]:
                self.writeln('      {0}'.format(l))
            if (len(ncline) + 6) > self.pagewidth:
              # code is too long, must break
              #self.writeln('line:{0} tokens:{1}'.format(len(ncline), len(noncomments)))
              try:
                broken = wrap_code(ncline, self.pagewidth-6)
              except tokenize.TokenError:
                # Can't tokenize, so we just wrap this with the same wrapping used
                # for noncode and hope for the best.
                broken = wrap_comment(ncline, self.pagewidth-6)
              self.writeln('{0:>4}* {1}'.format(i+1, broken[0]))
              for l in broken[1:]:
                self.writeln('      {0}'.format(l))
            else:
              self.writeln('{0:>4}: {1}'.format(i+1, ncline))
          else:
            # Only comments on this line
            c_wrap = wrap_comment(line, self.pagewidth-6)
            self.writeln( '{0:>4}: {1}'.format(i+1, c_wrap[0]) )
            for l in c_wrap[1:]:
              self.writeln('      {0}'.format(l))
          """
        else:
          # Line fits on page
          self.writeln( '{0:>4}: {1}'.format(i+1, line.rstrip()) )

  def display_pep8(self, path, summary=True):
    pep8_out = StringIO()
    try:
      with RedirectedIO(target=pep8_out, close_target=False):
        pep8.process_options([path])
        pep8.input_file(path)
        error_stats = pep8.get_error_statistics()
        warning_stats = pep8.get_warning_statistics()
      val = pep8_out.getvalue().splitlines()
      for line in [ x.split(':',1)[1] for x in val if ':' in x]:
        self.writeln(line)

      if summary:
        self.writeln()
        self.writeln("Summary:")
        for e in error_stats:
          self.writeln(e)
        for w in warning_stats:
          self.writeln(w)
        self.writeln()
    except tokenize.TokenError:
      self.boxed_text(["PEP8 processing failed - check your source code"], symbol="#")

# adapted from http://code.activestate.com/recipes/473878/
class TimeOutExceeded(Exception): pass

class KThread(threading.Thread):
  """A subclass of threading.Thread, with a kill() method."""
  def __init__(self, *args, **keywords):
    threading.Thread.__init__(self, *args, **keywords)
    self.killed = False
    self.result = None 

  def start(self):
    """Start the thread."""
    self.__run_backup = self.run
    self.run = self.__run      # Force the Thread to install our trace.
    threading.Thread.start(self)

  def run(self):
    # TODO: Capture STDOUT, STDERR
    success = True
    outstream = StringIO()
    try:
      with RedirectedIO(target=outstream, close_target=False):
        val = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
    except Exception, e:
      val = sys.exc_info()
      success = False
    output = outstream.getvalue()
    self.result = success, val, output

  def __run(self):
    """Hacked run function, which installs the trace."""
    sys.settrace(self.globaltrace)
    self.__run_backup()
    self.run = self.__run_backup

  def globaltrace(self, frame, why, arg):
    if why == 'call':
      return self.localtrace
    else:
      return None

  def localtrace(self, frame, why, arg):
    if self.killed:
      if why == 'line':
        raise SystemExit()
    return self.localtrace

  def kill(self):
    self.killed = True

def timeout(func, args=(), kwargs={}, timeout_duration=10, default=None):
    """This function will spawn a thread and run the given function
    using the args, kwargs and return the given default value if the
    timeout_duration is exceeded.
    """ 
    if isinstance(args, basestring):
      args = eval(args)
    if isinstance(kwargs, basestring):
      kwargs = eval(kwargs)
    t = KThread(target=func, args=args, kwargs=kwargs)
    t.start()
    t.join(timeout_duration)
    if t.isAlive():
        t.kill()
        raise TimeOutExceeded()
    else:
        return t.result


@contextlib.contextmanager
def working_directory(path):
    prev_cwd = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(prev_cwd)
