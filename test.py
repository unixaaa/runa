import runac
import sys, os, unittest, subprocess, json

DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(DIR, 'tests')
TESTS = [i[:-4] for i in os.listdir(TEST_DIR) if i.endswith('.rns')]

def run(self, key):
	
	fullname = os.path.join(TEST_DIR, key + '.rns')
	base = fullname.rsplit('.rns', 1)[0]
	bin = base + '.test'
	
	spec = {}
	with open(fullname) as f:
		h = f.readline()
		if h.startswith('# test: '):
			spec.update(json.loads(h[8:]))
	
	out = None
	try:
		runac.compile(fullname, bin)
	except runac.Error as e:
		out = e.show(fullname)
	
	if not out:
		out = subprocess.check_output([bin] + spec.get('args', []))
	
	if os.path.exists(base + '.out'):
		expected = open(base + '.out').read()
	else:
		expected = ''
	
	if self is None:
		return expected == out
	else:
		self.assertMultiLineEqual(expected, out)

def testfunc(key):
	def do(self):
		return self._do(key)
	return do

attrs = {'_do': run}
for key in TESTS:
	m = testfunc(key)
	m.__name__ = 'test_%s' % key
	attrs[m.__name__] = m

LangTests = type('LangTests', (unittest.TestCase,), attrs)

def suite():
    return unittest.makeSuite(LangTests, 'test')

if __name__ == '__main__':
	if len(sys.argv) > 1:
		print run(None, sys.argv[1])
	else:
	    unittest.main(defaultTest='suite')
