import types

class PrettyPrinter(object):
	
	def __init__(self):
		self.buf = []
	
	def newline(self):
		self.buf.append('\n')
	
	def write(self, data):
		assert isinstance(data, str), data
		self.buf.append(data)
	
	def writeline(self, ln):
		if not ln: return
		self.write(ln + '\n')
	
	def visit(self, node):
		if isinstance(node, types.base):
			self.type(node)
		else:
			getattr(self, node.__class__.__name__)(node)
	
	def build(self, name, fun):
		
		name = '.'.join(name) if isinstance(name, tuple) else name
		self.start = False
		self.write('def %s(' % name)
		for i, node in enumerate(fun.args):
			self.visit(node)
			if i < len(fun.args) - 1:
				self.write(', ')
		
		self.write(')')
		if fun.rtype is not None:
			self.write(' -> ')
			self.visit(fun.rtype)
		
		self.write(':')
		self.newline()
		
		for i, bl in fun.flow.blocks.iteritems():
			self.writeline('  %2i:' % i)
			for sid, step in enumerate(bl.steps):
				self.write(' {%02i} ' % sid)
				self.visit(step)
				self.newline()
		
		return ''.join(self.buf)
	
	def type(self, node):
		self.write(node.name)
	
	def anno(self, node):
		
		if node.type is None and not getattr(node, 'escapes', False):
			return
		
		if isinstance(node.type, (types.function, types.Type)):
			return
		
		self.write(' [')
		if node.type is not None:
			self.visit(node.type)
		
		if node.type is not None and getattr(node, 'escapes', False):
			self.write(':')
		
		if getattr(node, 'escapes', False):
			self.write('E')
		
		self.write(']')
	
	def Name(self, node):
		self.write(node.name)
		self.anno(node)
	
	def Bool(self, node):
		self.write(str(node.val))
		self.anno(node)
	
	def Int(self, node):
		self.write(str(node.val))
		self.anno(node)
	
	def Float(self, node):
		self.write(str(node.val))
		self.anno(node)
	
	def String(self, node):
		self.write(repr(node.val))
		self.anno(node)
	
	def binary(self, op, node):
		self.write(op + ' ')
		self.visit(node.left)
		self.write(' ')
		self.visit(node.right)
	
	def As(self, node):
		self.binary('As', node)
	
	def Not(self, node):
		self.write('Not ')
		self.visit(node.value)
	
	def And(self, node):
		self.binary('And', node)
	
	def Or(self, node):
		self.binary('Or', node)
	
	def NE(self, node):
		self.binary('NE', node)
	
	def GT(self, node):
		self.binary('GT', node)
	
	def LT(self, node):
		self.binary('LT', node)
	
	def EQ(self, node):
		self.binary('EQ', node)
	
	def Add(self, node):
		self.binary('Add', node)
	
	def Sub(self, node):
		self.binary('Sub', node)
	
	def Mul(self, node):
		self.binary('Mul', node)
	
	def Div(self, node):
		self.binary('Div', node)
	
	def Pass(self, node):
		self.write('Pass')
	
	def Init(self, node):
		self.write('Init ')
		self.visit(node.type)
	
	def Ref(self, node):
		self.write('&')
		self.visit(node.value)
	
	def Owner(self, node):
		self.write('$')
		self.visit(node.value)
	
	def Argument(self, node):
		self.write(node.name.name)
		self.anno(node)
		
	def Assign(self, node):
		self.visit(node.left)
		self.write(' = ')
		self.visit(node.right)
	
	def Call(self, node):
		self.visit(node.name)
		self.write('(')
		for i, arg in enumerate(node.args):
			self.visit(arg)
			if i < len(node.args) - 1:
				self.write(', ')
		self.write(')')
		self.anno(node)
	
	def Return(self, node):
		self.write('Return')
		if node.value is not None:
			self.write(' ')
			self.visit(node.value)
	
	def Yield(self, node):
		self.write('Yield')
		if node.value is not None:
			self.write(' ')
			self.visit(node.value)
	
	def CondBranch(self, node):
		self.write('CondBranch ')
		self.visit(node.cond)
		self.write(' ? %s : %s' % (node.tg1, node.tg2))
	
	def Branch(self, node):
		self.write('Branch %s' % node.label)
	
	def Attrib(self, node):
		self.visit(node.obj)
		self.write(' . ')
		self.write(node.attrib)
		self.anno(node)
	
	def SetAttr(self, node):
		self.Attrib(node)
	
	def Elem(self, node):
		self.write('Elem(')
		self.visit(node.obj)
		self.write(', ')
		self.visit(node.key)
		self.write(')')
		self.anno(node)
	
	def Phi(self, node):
		self.write('Phi ')
		self.write('%s:' % node.left[0])
		self.visit(node.left[1])
		self.write(', ')
		self.write('%i:' % node.right[0])
		self.visit(node.right[1])
	
	def For(self, node):
		self.visit(node.lvar)
		self.write(' <- ')
		self.visit(node.source)
	
	def LoopSetup(self, node):
		self.write('LoopSetup ')
		self.visit(node.loop)
	
	def LoopHeader(self, node):
		self.write('LoopHeader ctx:')
		self.visit(node.ctx)
		self.write(' lvar:')
		self.visit(node.lvar)
		self.write(' %s:%s' % (node.tg1, node.tg2))

def prettify(name, flow):
	pp = PrettyPrinter()
	return pp.build(name, flow)