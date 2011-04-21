import os
import shutil
import tempfile
import unittest

from subprocess import Popen, PIPE

from cpybuilder import *


# FIXME: this will need tweaking:
pyruntimes = [PyRuntime('/usr/bin/python2.7', '/usr/bin/python2.7-config'),
              PyRuntime('/usr/bin/python2.7-debug', '/usr/bin/python2.7-debug-config'),
              PyRuntime('/usr/bin/python3.2mu', '/usr/bin/python3.2mu-config'),
              #PyRuntime('/usr/bin/python3.2dmu', '/usr/bin/python3.2dmu-config')
              ]

class CompilationError(CommandError):
    def __init__(self, bm, out, err, p):
        CommandError.__init__(self, out, err, p)
        self.bm = bm
    
    def _describe_activity(self):
        return 'compiling: %s' % ' '.join(self.bm.args)

class BuiltModule:
    """A test build of a SimpleModule for a PyRuntime, done in a tempdir"""
    def __init__(self, sm, runtime):
        self.sm = sm
        self.runtime = runtime

        self.tmpdir = tempfile.mkdtemp()

        self.srcfile = os.path.join(self.tmpdir, 'example.c')
        self.modfile = os.path.join(self.tmpdir, runtime.get_module_filename('example'))

        f = open(self.srcfile, 'w')
        f.write(sm.cu.as_str())
        f.close()
        
        cflags = runtime.get_build_flags()
        self.args = ['gcc']
        self.args += ['-o', self.modfile]
        self.args += cflags.split()
        self.args += ['-Wall',  '-Werror'] # during testing
        self.args += ['-shared'] # not sure why this is necessary
        self.args += [self.srcfile]
        #print self.args

        # Invoke the compiler:
        p = Popen(self.args, stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()
        c = p.wait()
        if c != 0:
            raise CompilationError(self, out, err, p)

        assert os.path.exists(self.modfile)

    def run_command(self, cmd):
        """Run the command (using the appropriate PyRuntime), adjusting sys.path first"""
        out = self.runtime.run_command('import sys; sys.path.append("%s"); %s' % (self.tmpdir, cmd))
        return out

    def cleanup(self):
        shutil.rmtree(self.tmpdir)

class SimpleTest(unittest.TestCase):
    #def __init__(self, pyruntime):
    #    self.pytun
    def test_simple_compilation(self):
        # Verify building and running a trivial module (against multiple Python runtimes)
        sm = SimpleModule()

        sm.cu.add_decl("""
static PyObject *
example_hello(PyObject *self, PyObject *args);
""")

        sm.cu.add_defn("""
static PyObject *
example_hello(PyObject *self, PyObject *args)
{
    return Py_BuildValue("s", "Hello world!");
}
""")

        methods = PyMethodTable('example_methods',
                                [PyMethodDef('hello', 'example_hello',
                                             METH_VARARGS, 'Return a greeting.')])
        sm.cu.add_defn(methods.c_defn())

        sm.add_module_init('example', modmethods=methods, moddoc='This is a doc string')
        # print sm.cu.as_str()

        for runtime in pyruntimes:
            # Build the module:
            bm = BuiltModule(sm, runtime)

            # Verify that it built:
            out = bm.run_command('import example; print(example.hello())')
            self.assertEqual(out, "Hello world!\n")
        
            # Cleanup successful test runs:
            bm.cleanup()

    def test_module_with_type(self):
        # Verify an extension with a type
        sm = SimpleModule()

        sm.cu.add_decl("""
struct PyExampleType {
     PyObject_HEAD
     int i;
};
""")

        sm.add_type_object(name = 'example_ExampleType',
                           localname = 'ExampleType',
                           tp_name = 'example.ExampleType',
                           struct_name = 'struct PyExampleType')

        sm.add_module_init('example', modmethods=None, moddoc='This is a doc string')
        # print sm.cu.as_str()

        for runtime in pyruntimes:
            # Build the module:
            bm = BuiltModule(sm, runtime)

            # Verify that it built:
            out = bm.run_command('import example; print(example.ExampleType)')
            if runtime.is_py3k():
                self.assertEquals(out, "<class 'example.ExampleType'>\n")
            else:
                self.assertEquals(out, "<type 'example.ExampleType'>\n")

            # Cleanup successful test runs:
            bm.cleanup()

    def test_version_parsing(self):
        vi  = PyVersionInfo.from_text("sys.version_info(major=2, minor=7, micro=1, releaselevel='final', serial=0)")
        self.assertEqual(vi,
                         PyVersionInfo(major=2, minor=7, micro=1, releaselevel='final', serial=0))

        # "sys.version_info(major=2, minor=7, micro=1, releaselevel='final', serial=0)"
        # "sys.version_info(major=3, minor=2, micro=0, releaselevel='candidate', serial=1)"

                         


if __name__ == '__main__':
    unittest.main()
