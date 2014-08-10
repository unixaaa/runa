import types, ast, blocks, util

class Object(util.AttribRepr):
	def __init__(self, type):
		self.type = type

class Init(ast.Expr):
	def __init__(self, type):
		ast.Expr.__init__(self, None)
		self.type = type

class Module(util.AttribRepr):
	
	def __init__(self, name, init):
		self.name = name
		self.attribs = init
		self.type = types.module(name)
		for k, val in init.iteritems():
			if isinstance(val, types.FunctionDef):
				self.type.functions[k] = val.type
				val.name = '%s.%s' % (name, k)
	
	def __getitem__(self, key):
		return self.attribs[key]
	
	def __contains__(self, key):
		return key in self.attribs
	
	def iteritems(self):
		return self.attribs.iteritems()

class Decl(object):
	
	def __init__(self, name, rtype, atypes):
		self.decl = name
		self.rtype = rtype
		self.atypes = atypes
	
	def __repr__(self):
		name = self.__class__.__name__
		atypes = ', '.join(self.atypes)
		return '<%s(%r, %s, (%s))>' % (name, self.decl, self.rtype, atypes)

ROOT = Module('', {
	'__internal__': Module('__internal__', {
		'__malloc__': Decl('runa.malloc', '$byte', ('uint',)),
		'__free__': Decl('runa.free', 'void', ('$byte',)),
		'__memcpy__': Decl('runa.memcpy', 'void', ('&byte', '&byte', 'uint')),
		'__offset__': Decl('runa.offset', '&byte', ('&byte', 'uint')),
	}),
	'libc': Module('libc', {
		'stdlib': Module('libc.stdlib', {
			'getenv': Decl('getenv', '&byte', ('&byte',)),
		}),
		'stdio': Module('libc.stdio', {
			'snprintf': Decl('snprintf', 'i32', (
				'&byte', 'i32', '&byte', '...'
			)),
		}),
		'string': Module('libc.string', {
			'strncmp': Decl('strncmp', 'i32', ('&byte', '&byte', 'uint')),
			'strlen': Decl('strlen', 'uint', ('&byte',)),
		}),
		'unistd': Module('libc.unistd', {
			'write': Decl('write', 'int', ('i32', '&byte', 'uint')),
		}),
	}),
})

def resolve(mod, n):
	parts = n.split('.')
	if parts[0] in mod.scope:
		return mod.scope[parts[0]]
	elif parts[0] in ROOT:
		obj = ROOT
		for p in parts:
			obj = obj[p]
		return obj
	elif parts[0] in mod.names:
		method = mod.names[parts[0]].methods[parts[1]]
		mt = types.function(method[1], method[2])
		return types.FunctionDef(method[0], mt)
	elif parts[0] in types.ALL:
		method = types.get(parts[0]).methods[parts[1]]
		mt = types.function(method[1], method[2])
		return types.FunctionDef(method[0], mt)
	else:
		assert False, 'cannot resolve %s' % (tuple(parts),)

class Scope(object):
	
	def __init__(self, parent=None):
		self.parent = parent
		self.vars = {}
	
	def __repr__(self):
		return '<Scope(%r)>' % self.vars
	
	def __contains__(self, key):
		if key in self.vars:
			return True
		elif self.parent is not None:
			return key in self.parent
		else:
			return False
	
	def __getitem__(self, key):
		if key in self.vars:
			return self.vars[key]
		elif self.parent is not None and key in self.parent:
			return self.parent[key]
		else:
			raise KeyError(key)
	
	def __setitem__(self, key, val):
		self.vars[key] = val
	
	def __delitem__(self, key):
		del self.vars[key]
	
	def get(self, key, default=None):
		return self[key] if key in self else default
	
	def resolve(self, node):
		if isinstance(node, ast.Name) and node.name not in self:
			raise util.Error(node, "type '%s' not found" % node.name)
		if isinstance(node, ast.Name):
			assert self[node.name].type == types.Type()
			return self[node.name]
		elif isinstance(node, ast.Elem):
			inner = self.resolve(node.key)
			return self[node.obj.name][inner]
		elif isinstance(node, ast.Tuple):
			return types.build_tuple(self.resolve(v) for v in node.values)
		elif isinstance(node, ast.Ref):
			return types.ref(self.resolve(node.value))
		elif isinstance(node, ast.Owner):
			return types.owner(self.resolve(node.value))
		else:
			assert False

class TypeChecker(object):
	
	def __init__(self, mod, fun):
		self.mod = mod
		self.fun = fun
		self.flow = fun.flow
		self.scopes = {}
		self.cur = None, None
	
	def check(self, scope):
		self.scopes[None] = scope
		for i, b in sorted(self.flow.blocks.iteritems()):
			scope = self.scopes[i] = Scope()
			for sid, step in enumerate(b.steps):
				self.cur = b, sid
				self.visit(step, scope)
	
	def visit(self, node, scope):
		getattr(self, node.__class__.__name__)(node, scope)
	
	# Constants
	
	def Name(self, node, scope, strict=True):
		
		defined = []
		for id in self.cur[0].origin[node.name, self.cur[1]]:
			
			if id not in self.scopes:
				continue
			
			if id == self.cur[0].id:
				assigned = min(self.cur[0].assigns[node.name])
				if self.cur[1] <= assigned:
					continue
			
			defined.append(self.scopes[id].get(node.name))
		
		if not strict:
			defined = [i for i in defined if i is not None]
		if not defined or not all(defined):
			raise util.Error(node, "undefined name '%s'" % node.name)
		
		first = defined[0].type
		for n in defined:
			assert n.type == first
		
		node.type = first
	
	def NoneVal(self, node, scope):
		node.type = types.get('NoType')
	
	def Bool(self, node, scope):
		node.type = types.get('bool')
	
	def Int(self, node, scope):
		node.type = types.anyint()
	
	def Float(self, node, scope):
		node.type = types.anyfloat()
	
	def String(self, node, scope):
		node.type = types.owner(types.get('str'))
	
	def Tuple(self, node, scope):
		for v in node.values:
			self.visit(v, scope)
		node.type = types.build_tuple(v.type for v in node.values)
	
	# Boolean operators
	
	def Not(self, node, scope):
		self.visit(node.value, scope)
		node.type = types.get('bool')
	
	def boolean(self, op, node, scope):
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		if node.left.type == node.right.type:
			node.type = node.left.type
		else:
			node.type = types.get('bool')
	
	def And(self, node, scope):
		self.boolean('and', node, scope)
	
	def Or(self, node, scope):
		self.boolean('or', node, scope)
	
	# Comparison operators
	
	def Is(self, node, scope):
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		assert isinstance(node.right, ast.NoneVal), node.right
		assert isinstance(node.left.type, types.WRAPPERS), node.left
		node.type = types.get('bool')
	
	def compare(self, op, node, scope):
		
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		
		lt, rt = types.unwrap(node.left.type), types.unwrap(node.right.type)
		if node.left.type == node.right.type:
			node.type = types.get('bool')
		elif lt in types.INTS and rt not in types.INTS:
			msg = "value of type '%s' may only be compared to integer type"
			raise util.Error(node, msg % node.left.type.name)
		elif lt in types.FLOATS and rt not in types.FLOATS:
			msg = "value of type '%s' may only be compared to float type"
			raise util.Error(node, msg % node.left.type.name)
		elif lt not in types.INTS and lt not in types.FLOATS:
			msg = "types '%s' and '%s' cannot be compared"
			raise util.Error(node, msg % (lt.name, rt.name))
		
		node.type = types.get('bool')
	
	def EQ(self, node, scope):
		self.compare('eq', node, scope)
	
	def NE(self, node, scope):
		self.compare('ne', node, scope)
	
	def LT(self, node, scope):
		self.compare('lt', node, scope)
	
	def GT(self, node, scope):
		self.compare('gt', node, scope)
	
	# Arithmetic operators
	
	def arith(self, op, node, scope):
		
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		
		lt, rt = types.unwrap(node.left.type), types.unwrap(node.right.type)
		if node.left.type == node.right.type:
			node.type = node.left.type
		elif lt in types.INTS:
			assert rt in types.INTS
			node.type = node.left.type
		else:
			assert False, op + ' sides different types'
	
	def Add(self, node, scope):
		self.arith('add', node, scope)
	
	def Sub(self, node, scope):
		self.arith('sub', node, scope)
	
	def Mod(self, node, scope):
		self.arith('mod', node, scope)
	
	def Mul(self, node, scope):
		self.arith('mul', node, scope)
	
	def Div(self, node, scope):
		self.arith('div', node, scope)
	
	# Bitwise operators
	
	def bitwise(self, op, node, scope):
		
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		
		lt, rt = types.unwrap(node.left.type), types.unwrap(node.right.type)
		if node.left.type == node.right.type:
			node.type = node.left.type
		elif lt in types.INTS:
			assert rt in types.INTS
			node.type = node.left.type
		else:
			msg = "bitwise operations do not apply to '%s', '%s'"
			raise util.Error(node, msg % (lt.name, rt.name))
		
		node.type = node.left.type
	
	def BWAnd(self, node, scope):
		self.bitwise('and', node, scope)
	
	def BWOr(self, node, scope):
		self.bitwise('or', node, scope)
	
	def BWXor(self, node, scope):
		self.bitwise('xor', node, scope)
	
	# Iteration-related nodes
	
	def Yield(self, node, scope):
		self.visit(node.value, scope)
		assert self.fun.rtype.params[0] == node.value.type
	
	def LoopSetup(self, node, scope):
		
		self.visit(node.loop.source, scope)
		t = types.unwrap(node.loop.source.type)
		if not t.name.startswith('iter['):
			call = ast.Call(None)
			call.name = ast.Attrib(None)
			call.name.obj = node.loop.source
			call.name.attrib = '__iter__'
			call.args = []
			call.fun = None
			call.virtual = None
			self.visit(call, scope)
			node.loop.source = call
		
		name = node.loop.source.fun.name + '$ctx'
		node.type = types.get(name)
		self.mod.variants.add(node.type)
	
	def LoopHeader(self, node, scope):
		
		name = node.lvar.name
		vart = node.ctx.type.yields
		if name in scope and scope[name].type != vart:
			assert False, 'reassignment'
		
		scope[name] = Object(vart)
		node.lvar.type = vart
	
	# Miscellaneous
	
	def As(self, node, scope):
		self.visit(node.left, scope)
		node.type = self.scopes[None][node.right.name]
	
	def Raise(self, node, scope):
		self.visit(node.value, scope)
		assert node.value is not None
	
	def Attrib(self, node, scope):
		
		self.visit(node.obj, scope)
		t = node.obj.type
		if isinstance(t, types.WRAPPERS):
			t = t.over
		
		node.type = t.attribs[node.attrib][1]
		assert node.type is not None, 'FAIL'
		if isinstance(node.type, types.owner):
			node.type = types.ref(node.type.over)
	
	def SetAttr(self, node, scope):
		
		self.visit(node.obj, scope)
		t = node.obj.type
		if isinstance(t, types.WRAPPERS):
			t = t.over
		
		node.type = t.attribs[node.attrib][1]
		assert node.type is not None, 'FAIL'
	
	def Elem(self, node, scope):
		self.visit(node.key, scope)
		self.visit(node.obj, scope)
		objt = types.unwrap(node.obj.type)
		assert objt.name.startswith('array['), objt
		node.type = objt.attribs['data'][1].over
	
	def Call(self, node, scope):
		
		actual = []
		for arg in node.args:
			self.visit(arg, scope)
			actual.append(arg.type)
		
		if isinstance(node.name, ast.Attrib):
			
			if node.name.obj.type is None:
				self.visit(node.name.obj, scope)
			
			if node.name.obj.type == types.module():
				
				# calling a module attribute
				mod = scope[node.name.obj.name]
				fun = mod.type.functions[node.name.attrib.name]
				qual = mod.name + '.' + node.name.attrib.name
				node.fun = types.FunctionDef(qual, fun)
				node.type = fun.over[0]
				
			else:
				
				# calling an object attribute (method)
				t = types.unwrap(node.name.obj.type)
				if isinstance(t, types.trait):
					node.virtual = True
				
				node.args.insert(0, node.name.obj)
				actual = [a.type for a in node.args]
				node.fun = t.select(node, node.name.attrib, actual)
				node.type = node.fun.type.over[0]
			
			if not types.compat(actual, node.fun.type.over[1]):
				assert False
			
			for i, (a, f) in enumerate(zip(actual, node.fun.type.over[1])):
				if isinstance(f, types.owner):
					if isinstance(node.args[i], ast.Name):
						del scope[node.args[i].name]
			
			return
		
		self.visit(node.name, scope)
		allowed = types.function, types.Type
		if not isinstance(node.name.type, allowed):
			msg = 'object is not a function'
			raise util.Error(node.name, msg)
		
		obj = self.scopes[None][node.name.name]
		if not isinstance(obj, types.base):
			
			# calling a function
			node.fun = obj
			node.type = node.fun.type.over[0]
			if not types.compat(actual, node.fun.type.over[1]):
				astr = ', '.join(t.name for t in actual)
				fstr = ', '.join(t.name for t in node.fun.type.over[1])
				msg = 'arguments (%s) cannot be passed as (%s)'
				raise util.Error(node, msg % (astr, fstr))
			
		else:
			
			# initializing a type
			node.fun = obj.select(node, '__init__', actual)
			node.name.name = node.fun.decl
			node.type = types.owner(obj)
			if '__init__' in node.fun.decl:
				node.args.insert(0, Init(types.owner(obj)))
		
		for i, (a, f) in enumerate(zip(actual, node.fun.type.over[1])):
			if isinstance(f, types.owner):
				if isinstance(node.args[i], ast.Name):
					del scope[node.args[i].name]
		
		if isinstance(obj, types.FunctionDef):
			node.name.name = obj.name
	
	def CondBranch(self, node, scope):
		self.visit(node.cond, scope)
	
	def Assign(self, node, scope):
		
		if isinstance(node.left, ast.Tuple):
			
			ttypes = []
			self.visit(node.right, scope)
			assert node.right.type.name.startswith('tuple[')
			for i, dst in enumerate(node.left.values):
				
				assert isinstance(dst, ast.Name)
				t = node.right.type.params[i]
				if dst in scope and scope[dst.name].type != t:
					assert False, 'reassignment'
				
				assert t is not None
				scope[dst.name] = Object(t)
				dst.type = t
				ttypes.append(t)
			
			node.left.type = types.build_tuple(ttypes)
			return
		
		if not isinstance(node.left, ast.Name):
			
			self.visit(node.left, scope)
			self.visit(node.right, scope)
			if node.left.type != node.right.type:
				bits = node.right.type.name, node.left.type.name
				msg = 'incorrect assignment of %s to %s'
				raise util.Error(node, msg % bits)
			
			return
		
		name = node.left.name
		self.visit(node.right, scope)
		if name in scope and scope[name].type != node.right.type:
			assert False, 'reassignment'
		
		assert node.right.type is not None
		scope[node.left.name] = node.right
		node.left.type = node.right.type
	
	def Phi(self, node, scope):
		
		if isinstance(node.left[1], ast.Name):
			self.Name(node.left[1], scope, strict=False)
		else:
			self.visit(node.left[1], scope)
		
		if isinstance(node.right[1], ast.Name):
			self.Name(node.right[1], scope, strict=False)
		else:
			self.visit(node.right[1], scope)
		
		if node.left[1].type == node.right[1].type:
			node.type = node.left[1].type
		else:
			bits = tuple(i.type.name for i in (node.left[1], node.right[1]))
			raise util.Error(node, "unmatched types '%s', '%s'" % bits)
	
	def LPad(self, node, scope):
		for type in node.map:
			t = types.get(type)
			assert t.name == 'Exception'
	
	def Branch(self, node, scope):
		return
	
	def Pass(self, node, scope):
		return
	
	def Return(self, node, scope):
		
		if self.flow.yields:
			assert node.value is None
			return
		
		if node.value is None and self.fun.rtype != types.void():
			msg = "function may not return value of type 'void'"
			raise util.Error(node, msg)
		elif node.value is not None and self.fun.rtype == types.void():
			msg = "function must return type 'void' ('%s' not allowed)"
			self.visit(node.value, scope)
			raise util.Error(node, msg % (node.value.type.name))
		elif node.value is None:
			return
		
		self.visit(node.value, scope)
		if not types.compat(node.value.type, self.fun.rtype):
			msg = "return value does not match declared return type '%s'"
			raise util.Error(node, msg % self.fun.rtype.name)

def variant(mod, t):
	if isinstance(t, types.WRAPPERS):
		variant(mod, t.over)
	elif hasattr(t, 'over') or isinstance(t, types.concrete):
		mod.variants.add(t)

VOID = {'__init__', '__del__'}

def process(mod, base, fun):
	
	if fun.name.name in VOID and fun.rtype is not None:
		msg = "method '%s' must return type 'void'"
		raise util.Error(fun.rtype, msg % fun.name.name)
	
	start = Scope(base)
	if fun.rtype is None:
		fun.rtype = types.void()
	if not isinstance(fun.rtype, types.base):
		fun.rtype = start.resolve(fun.rtype)
		variant(mod, fun.rtype)
	
	for arg in fun.args:
		
		if arg.type is None:
			msg = "missing type for argument '%s'"
			raise util.Error(arg, msg % arg.name.name)
		
		if not isinstance(arg.type, types.base):
			arg.type = start.resolve(arg.type)
		
		start[arg.name.name] = arg
		variant(mod, arg.type)
	
	if fun.flow.yields:
		
		if '.' in fun.irname:
			mcls = types.unwrap(fun.args[0].type)
			defn = mcls.methods[fun.name.name][0]
		else:
			defn = base[fun.name.name]
		
		name = fun.irname + '$ctx'
		cls = types.ALL[name] = type(name, (types.concrete,), {
			'name': name,
			'ir': '%' + name,
			'yields': fun.rtype.params[0],
			'function': defn,
			'attribs': {}
		})
	
	checker = TypeChecker(mod, fun)
	checker.check(start)

def typer(mod):
	
	for k, v in mod.names.iteritems():
		if isinstance(v, (ast.Class, ast.Trait)):
			types.add(v)
	
	base = Scope()
	base['iter'] = types.iter()
	for name, obj in mod.names.iteritems():
		
		if not isinstance(obj, basestring):
			continue
		
		ns = ROOT
		path = obj.split('.')
		while len(path) > 1:
			ns = ns.attribs[path.pop(0)]
		
		val = ns.attribs[path[0]]
		if isinstance(val, Decl):
			val = types.realize(val)
		
		mod.names[name] = base[name] = val
	
	for k, v in mod.names.iteritems():
		if not isinstance(v, blocks.Constant):
			continue
		if isinstance(v.node, ast.String):
			v.node.type = types.get('&str')
		elif isinstance(v.node, ast.Int):
			v.node.type = types.get('&int')
		else:
			assert False, v.node
		base[k] = v.node
	
	for k, v in mod.names.iteritems():
		if isinstance(v, (ast.Class, ast.Trait)):
			base[k] = mod.names[k] = types.fill(v)
	
	for k, v in mod.names.iteritems():
		if isinstance(v, ast.Decl):
			base[k] = mod.names[k] = types.realize(v)
	
	for k, fun in mod.code:
		
		if not isinstance(k, basestring):
			continue
		
		atypes = []
		anames = []
		for arg in fun.args:
			if arg.type is None:
				msg = "missing type for argument '%s'"
				raise util.Error(arg, msg % arg.name.name)
			atypes.append(base.resolve(arg.type))
			anames.append(arg.name.name)
		
		rtype = types.void() if fun.rtype is None else base.resolve(fun.rtype)
		type = types.function(rtype, atypes)
		type.args = anames
		base[fun.name.name] = types.FunctionDef(fun.name.name, type)
		fun.irname = fun.name.name
		
		if k == 'main' and atypes and atypes[0] != types.ref(base['str']):
			msg = '1st argument to main() must be of type &str'
			raise util.Error(fun.args[0].type, msg)
		
		compare = types.ref(base['array'][base['str']])
		if k == 'main' and atypes and atypes[1] != compare:
			msg = '2nd argument to main() must be of type &array[str]'
			raise util.Error(fun.args[1].type, msg)
		
		if k == 'main' and rtype not in {types.void(), base['i32']}:
			raise util.Error(fun, 'main() return type must be i32')
	
	mod.scope = base
	for k, fun in mod.code:
		
		if isinstance(k, tuple) and k[1] != '__new__':
			if not fun.args:
				raise util.Error(fun, "missing 'self' argument")
			elif fun.args[0].name.name != 'self':
				msg = "first method argument must be called 'self'"
				raise util.Error(fun.args[0], msg)
			elif fun.args[0].type is not None:
				if fun.args[0].type.name != k[0]:
					msg = "first method argument must be of type '%s'"
					raise util.Error(fun.args[0].type, msg % k[0])
		
		if fun.args and fun.args[0].type is None:
			if fun.name.name == '__del__':
				fun.args[0].type = types.owner(base[k[0]])
			else:
				fun.args[0].type = types.ref(base[k[0]])
		
		process(mod, base, fun)
