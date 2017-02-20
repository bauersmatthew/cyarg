"""A simple interface for CLI argument processing."""
import copy
import sys
import textwrap

def process(arg_descs, args=sys.argv[1:]):
    """Process a list of arguments.

    This function returns a dictionary containing the values read from argv of
    the arguments described by arg_descs.

    arg_descs: A list of argument descriptors. Each item in this list (each
    argument descriptor) must be a dict with required field:
      -  'n': The 'name' of the argument. If this value is a string, it is
              interpreted as either a single-character argument (e.g. '-a')
              or a string argument (e.g. '--all') depending on whether the
              value has more than one character or not (dashes should NOT be
              included in the value here!). If this value is a tuple of strings,
              each string in the tuple will be processed as described above and
              will be treated as synonyms. If this value is an int, the argument
              will be interpreted as being defined by its position in the arg
              list; e.g. in the list ['a', '4'] the 'a' is of position 1, and
              the '4' is of position 2. But, in the list ['-a', '4'],
              given that the '-a' argument does not expect a parameter after it,
              the position of '4' is 1 because it is the first positional arg in
              the list.
    And optional fields:
      -  't': The expected type of this argument. This value should be a
              callable that returns a variable with the desired type when given
              a single string; e.g., a class, primitive, or function. If this
              is field is not given and the argument is positionally defined,
              the type 'str' will be used. If this field is not given and the
              argument is defined by name, this argument will be interpreted as
              a 'switch' argument, and the value in the output dictionary will
              be either True if the switch is given in the arg list or False if
              it is not.
      -  'd': The default value of this argument. This is what is put into the
              output dictionary if the argument is not given in the arg list.
      -  'o': Whether or not this argument is optional. If not given, the arg
              is assumed to be required. If required arguments are not given,
              an exception is automatically thrown.
      -  'p': The name of this argument's parameter, if it has one. If this is
              not given, the type name is used instead. This is used for
              generating help messages.
      -  'desc': A (string) description of this argument. This is used for
                 generating help messages.

    argv: A list of string arguments, like given by sys.argv[1:].
    """
    return ArgLoader(arg_descs, copy.copy(args)).load_all()

def setup_argdesc_sdict(arg_descs):
    """Create a SynoDict that contains argument descriptors."""
    sdict = SynoDict()
    for desc in arg_descs:
        name = None
        if isinstance(desc['n'], tuple):
            sdict.register(desc['n'])
            name = desc['n'][0]
        else:
            name = desc['n']
        sdict[name] = desc
    return sdict


def setup_output_sdict(arg_descs):
    """Create a SynoDict that is aware of arg synonyms and defaults."""
    sdict = SynoDict()
    for desc in arg_descs:
        name = None
        if isinstance(desc['n'], tuple):
            sdict.register(desc['n'])
            name = desc['n'][0]
        else:
            name = desc['n']
        if 'd' in desc:
            sdict[name] = desc['d']
    return sdict

class ArgLoader(object):
    """Interface to load arguments. Keeps track of positional args."""
    def __init__(self, arg_descs, args):
        """Initialize with the same args as process() gets."""
        self.ml_args = MarkedList(args)
        self.arg_descs = arg_descs
        self.sd_out = setup_output_sdict(arg_descs)
        self.sd_descs = setup_argdesc_sdict(arg_descs)
        self.cur_positional = 1

    def load_all(self):
        """Get a dict of all options."""
        while self.ml_args:
            self.load_one()
        return self.sd_out.to_dict()

    def load_one(self):
        """Load one arg."""
        cur = self.ml_args.get()

        if len(cur) == 1 or cur[0] != '-' or cur == '--':
            # treat '-', '--' arguments as positional
            self.load_one_positional(cur)
        elif cur[1] != '-':
            self.load_one_1char(cur)
        else:
            self.load_one_nchar(cur)

    def load_one_positional(self, cur):
        """Load one positional arg/param."""
        self.sd_out[self.cur_positional] = self.try_translate(
            cur,
            self.try_recognize(self.cur_positional),
            self.cur_positional)
        self.cur_positional += 1

    def load_one_1char(self, cur):
        """Load a -XXX arg."""
        cur = cur[1:]
        focus = cur[0]
        is_single = len(cur) == 1
        argdesc = self.try_recognize(focus, '-' + focus)
        if 't' in argdesc:
            if is_single:
                self.sd_out[focus] = self.try_translate(
                    self.try_grab_next('-' + focus),
                    argdesc,
                    '-' + focus)
            else:
                # "trick" the sequencer
                # come back around and enter the above code seg
                # insert in reverse order!
                self.ml_args.lst.insert(self.ml_args.mark, cur[1:])
                self.ml_args.lst.insert(self.ml_args.mark, '-' + focus)
        else:
            if is_single:
                self.sd_out[focus] = True
            else:
                # "trick" the sequencer; basically just split apart the tokens
                # insert in reverse order!
                self.ml_args.lst.insert(self.ml_args.mark, '-' + cur[1:])
                self.ml_args.lst.insert(self.ml_args.mark, '-' + focus)

    def load_one_nchar(self, cur):
        """Load a --XXX arg."""
        cur = cur[2:]
        argdesc = self.try_recognize(cur, '--' + cur)
        if 't' in argdesc:
            self.sd_out[cur] = self.try_translate(
                self.try_grab_next('--' + cur),
                argdesc,
                '--' + cur)
        else:
            self.sd_out[cur] = True

    def try_recognize(self, name, print_name=None):
        """Tries to recognize an argument; raises exception if unrecognized."""
        try:
            return self.sd_descs[name]
        except:
            if not print_name:
                print_name = name
            raise RuntimeError(
                'Argument {0} not recognized!'.format(print_name))

    def try_translate(self, param, argdesc, name):
        """Try to translate a param given the argdesc."""
        val = param
        if 't' in argdesc:
            try:
                val = argdesc['t'](param)
            except:
                raise RuntimeError(
                    ("Value given for argument {0} ('{1}') could not be"
                     " understood!").format(name, param))
        return val

    def try_grab_next(self, name):
        """Attempt to grab the next value from the list."""
        if self.ml_args:
            return self.ml_args.get()
        else:
            raise RuntimeError(
                "Couldn't grab value for {0}!".format(name))

class SynoDict(dict):
    """A dict variant that ensures that values corresponding to key 'synonyms'
    are always the same.

    Only the [] operator is definitely safe!"""

    def __init__(self):
        """Initialize as an empty list, with no registered synonnyms."""
        super(self.__class__, self).__init__()
        self.syns = []

    def register(self, synlist):
        """Register an iterable of synonyms."""
        self.syns.append(synlist)

    def __setitem__(self, key, value):
        """Set an item, staying aware of synonyms."""
        to_set = self.__getsyns(key)
        for key in to_set:
            super(self.__class__, self).__setitem__(key, value)

    def __delitem__(self, key):
        """Delete an item, staying aware of synonyms."""
        to_del = self.__getsyns(key)
        for key in to_del:
            super(self.__class__, self).__delitem__(key)

    def __getsyns(self, key):
        """Get a list containing the given key and all its synonyms.

        Items may be duplicated in the list!"""
        syns = [key]
        for synlist in self.syns:
            if key in synlist:
                syns += synlist
        return syns

    def to_dict(self):
        """Get a shallow copy of the internal dict."""
        return copy.copy(super(self.__class__, self))

class MarkedList(object):
    """A list wrapper that keeps a "mark" to indicate the current location in
    the list."""

    def __init__(self, lst):
        """Initialize with the given list, and the mark at 0."""
        self.lst = lst
        self.mark = 0

    def get(self):
        """Return the value at the current mark, and increment the mark.

        Return None if the mark is past the end of the list."""
        if self.mark >= len(self.lst):
            return None
        ret = self.lst[self.mark]
        self.mark += 1
        return ret

    def get_silently(self):
        """Return the value at the current mark, WITHOUT incrementing the mark.

        Return None if the mark is past the end of the list."""
        if self.mark >= len(self.lst):
            return None
        return self.lst[self.mark]

    def __nonzero__(self):
        return self.mark < len(self.lst)

def print_help(help_info, arg_descs):
    """Print a sensible help message to stdout.

    help_info: A dictionary containing the keys 'name' and 'desc, which
               correspond to the name and description of the program
               respectively.

    arg_descs: A list of argument descriptors as defined by the 'process'
               function.
    """
    sys.stdout.write(get_help_message(help_info, arg_descs))

def get_help_message(help_info, arg_descs):
    """Get a sensible help message as a string.

    help_info: A dictionary containing the keys 'name' and 'desc, which
               correspond to the name and description of the program
               respectively.

    arg_descs: A list of argument descriptors as defined by the 'process'
               function.
    """
    # process args
    poss = []
    req_nonpos = []
    has_nonreqnonpos = False
    for desc in arg_descs:
        if isinstance(desc['n'], int):
            poss.append(desc)
        else:
            if 'o' in desc and desc['o']:
                req_nonpos.append(desc)
            else:
                has_nonreqnonpos = True

    ret = 'Usage: %s'%help_info['name']
    add_dashes = lambda n: ('-' if len(n) == 1 else '--') + n
    if has_nonreqnonpos:
        ret += ' [options]'
    for rnp in req_nonpos:
        name = None
        if isinstance(rnp['n'], tuple):
            name = add_dashes(rnp['n'][0])
        else:
            name = add_dashes(rnp['n'])
        parname = rnp['p'] if 'p' in rnp else rnp['t'].__name__
        ret += ' <%s %s>'%(name, parname)
    for posarg in poss:
        parname = posarg['p'] if 'p' in posarg else posarg['t'].__name__
        ret += ' {0}{1}{2}'.format(
            '[' if 'o' in posarg and posarg['o'] else '<',
            parname,
            ']' if 'o' in posarg and posarg['o'] else '>')
    ret += '\n\n%s'%(help_info['desc']+'\n\n' if 'desc' in help_info else '')

    ret += 'Options:\n'
    for desc in arg_descs:
        # -- MAKE SHORT-FORM --
        name = None
        if isinstance(desc['n'], int):
            name = desc['p'] if 'p' in desc else desc['t'].__name__
        elif isinstance(desc['n'], tuple):
            for alt_name in desc['n'][:-1]:
                ret += add_dashes(alt_name).rjust(20) + '\n'
            name = add_dashes(desc['n'][-1])
            if 't' in desc:
                name += (
                    ' ' +
                    (desc['p'] if 'p' in desc else desc['t'].__name__))
        else:
            name = add_dashes(desc['n'])
            if 't' in desc:
                name += (
                    ' ' +
                    (desc['p'] if 'p' in desc else desc['t'].__name__))

        ret += name.rjust(20)
        ret += '    ' # 4 spaces

        # -- ADD DESCRIPTION --
        if 'desc' in desc:
            descr_lines = textwrap.wrap(desc['desc'], 46) # 46 = 70 - 20 - 4
            ret += descr_lines[0] + '\n'
            for line in descr_lines[1:]:
                ret += (' '*24) + line + '\n' # 24 = 20 + 4
        else:
            ret += '\n'
        ret += '\n'

    return ret
