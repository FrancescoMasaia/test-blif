#! /usr/bin/python3


from subprocess import Popen, PIPE
import sys
import re
import prettytable
from  glob import glob

def main():
    verbose = '-v' in sys.argv
    if verbose:
        sys.argv.remove('-v')
    
    if len(sys.argv)==1 or sys.argv[1] in ['-h','--help']:
        full = '--help' in sys.argv
        print_help(full=full)
        exit(0)
    elif sys.argv[1] in ['-a', '--all']:
        run('*.blif',verbose=verbose)
    else:
        run(sys.argv[1],verbose=verbose)
        


def run(filename, verbose=False):
    file_list = glob(filename)
    file_list = list(sorted(file_list, key=lambda x: x.lower()))
    test_list = []
    for filename in file_list:
        tests = read_tests(filename)
        test_results = run_tests(filename,tests)
        test_list.append(test_results)
    
    print_summary(file_list,test_list)
    for filename,tests in zip(file_list,test_list):
        print_test_summary(filename,tests)
        print_test_details(filename,tests, verbose=verbose)
    
def read_tests(filename):
    comments = read_comments(filename)
    tests = []
    test=None
    in_test=False
    for c in comments:
        if c.startswith('#?#'):
            name = c[3:].strip()
            in_test = True
            test = Test(name)
            test.filename = filename
        elif c.startswith('#!#'):
            in_test = False
            tests.append(test)
        else:
            input,output = c.split('|',maxsplit=1)
            input = input[1:].strip()
            output = output.strip()
            test.inputs.append(input)
            test.outputs.append(output)
    return tests

def read_comments(filename):
    comments = []
    with open(filename) as f:
        lines = f.readlines()
        lines = [x.strip() for x in lines]
        for line in lines:
            if line.startswith('#'):
                comments.append(line)
    return comments


def run_tests(filename,tests):
    for test in tests:
        results, err = run_sims(filename,test.inputs)
        for res,correct in zip(results,test.outputs):
            correct = re.sub('[^01]', '', correct)
            test.results.append(res)
            test.validated.append(res == correct)
            test.errors += 0 if res == correct else 1
            test.warnings_sis = err
            if (res != correct):
                test.passed = False
    return tests


def print_summary(file_list,test_list):
    summary = prettytable.PrettyTable()
    
    summary.add_column("Filename",[],align='l')
    summary.add_column("Tests",[])
    summary.add_column("Failed",[])
    summary.add_column("Errors",[])
    summary.add_column("Result", [])
    summary.add_column("", [], align='l')
    
    summary.title = "SUMMARY"
    for filename, tests in zip(file_list,test_list):
        tests_num = len(tests)
        warnings_sis = tests[0].warnings_sis if tests_num > 0 else []
        failed = 0
        errors = 0
        for test in tests:
            failed += 0 if test.passed else 1
            errors += test.errors
        
        result = font_green('OK') if failed == 0 else font_red('ERROR')
        result = result if tests_num > 0 else font_yellow('NO TESTS')
        
        color = lambda x: x
        
        if errors>0:
            color=font_red
        else:
            color=font_green
        
        if tests_num==0:
            color = font_yellow
        
        summary.add_row([ color(filename), color(tests_num), color(failed), color(errors), color(result), '\n'.join(warnings_sis) ])
    print(summary.get_string(title="SUMMARY"), "\n")

        
def print_test_summary(filename,tests):
    test_summary = prettytable.PrettyTable()

    test_summary.add_column("N", [], align='r')
    test_summary.add_column("Name", [], align='l')
    test_summary.add_column("Errors", [])
    test_summary.add_column("Results", [])
    
    
    test_summary.title = "SUMMARY {}".format(filename)
    for i,test in enumerate(tests):
        color = lambda x: x
    
        if test.passed:
            color = font_green
        else:
            color = font_red
        
        passed = 'OK' if test.passed else 'ERROR'
        
        
        test_summary.add_row([ color(i+1),color(test.name),color(test.errors),color(passed)])
    if len(tests)>0:
        print(test_summary,"\n")

def print_test_details(filename, tests, verbose=False):
    details = False
    for i,test in enumerate(tests):
        if not test.passed or verbose:
            if not details:
                print("Details")
                details=True
            
            detail = prettytable.PrettyTable()
            
            detail.add_column("Input", [])
            detail.add_column("Output", [])
            detail.add_column("Expected", [])
            detail.add_column("Results", [])
            
            
            detail.title= "{} {}".format((i+1), test.name)
            for inp,res,out,val in zip(test.inputs,test.results,test.outputs,test.validated):
                out_format = re.sub('[01]', '{}', out)
                res_formatted = out_format.format( *list(res) )
                equal = [r if o not in ['0','1'] or o == r else font_red(r) for o, r in zip(out, res_formatted)]
                expected = [o if o not in ['0','1'] or o == r else font_green(o) for o, r in zip(out, res_formatted)]
                
                
                equal = ''.join(equal)
                expected = ''.join(expected)

                color = lambda x: x

                if val:
                    color = font_green
                else:
                    color = font_red

                response = color( 'OK' if val else 'ERROR' )
                
                
                
                detail.add_row( ( color(inp), equal, expected, response ) )
            print(detail,"\n")

    
    
def run_sims(filename,inputs):
    cmds = ['read_blif '+filename]
    for i in inputs:
        i = output = re.sub('[^01]','',i)
        cmds.append('sim ' + ' '.join(i))
    cmds.append("quit")
    out, err = run_sis(cmds)
    
    del (out[0])  # read_blif
    outputs = []
    for o in out:
        output = o[1].split(':')[1]
        output = re.sub('[^01]','',output)
        outputs.append(output)
    return outputs, err

def run_sis(cmds):
    sis = Popen("sis", stdin=PIPE, stdout=PIPE, stderr=PIPE, bufsize=-1, shell=True)
    cmd = '\n'.join(cmds)
    bcmd = (cmd).encode("utf-8")

    out, err = sis.communicate(input=bcmd)
    sis.stdin.close()
    sis.terminate()

    out = [ o.strip().split('\n') for o in out.decode('utf-8').strip().split('sis>')]
    err = err.decode('utf-8').strip().split('\n')
    del (out[:2]) # UC Berkeley ....
    del (err[0])
    return out, err

def font_color(text,color):
    # https://misc.flogisoft.com/bash/tip_colors_and_formatting
    return "\033[{}m{}\033[39m".format(color,text)

def font_red(text):
    return font_color(text,91)

def font_green(text):
    return font_color(text, 92)

def font_yellow(text):
    return font_color(text, 93)
    
def print_help(full=False):
        help = """
Print this help:
$ test_blif.py -h

Print this full help:
$ test_blif.py --help

Run tests of single blif file:
$ test_blif.py filename.blif

Run tests on all .blif in the folder:
$ test_blif.py [-a|--all]

"""
        print(help)
        if not full:
            return
        full_help="""
---
In order to add test to you blif file you can add comments in the following format directly in the file you want to test, suggested after the last ".end"
Multiple test can be added to a single .blif to address multiple scenarios. Each test runs independently from the others in new instance of SIS.

Test format:

#?# [Test_name_or_description]
# <inputs>|<expected_outputs>
# <inputs>|<expected_outputs>
# <inputs>|<expected_outputs>
#!#

Examples:

#?# Truth table OR
# 00 | 0
# 01 | 1
# 10 | 1
# 11 | 1
#!#

#?# 2 bit counter with overflow INC | C1 C0 COUT
# 1 | 00 0
# 1 | 01 0
# 1 | 10 0
# 1 | 11 0
# 1 | 00 1
#!#

---
Requirments:
python3
sudo -H pip3 install prettytable ptable

---
Software is provided AS IS, report issues at:
cesare.montresor@gmail.com

"""
        print(full_help)




class Test(object):
    def __init__(self,name=""):
        self.name = name
        self.inputs = []
        self.outputs = []
        self.results = []
        self.validated = []
        self.passed = True
        self.errors = 0
        self.filename = None
        self.warnings_sis = []
        
        
    
if __name__ == "__main__":
    main()