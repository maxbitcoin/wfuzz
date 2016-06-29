from framework.fuzzer.fuzzobjects import FuzzRequest
from framework.fuzzer.fuzzobjects import FuzzStats
from framework.core.facade import Facade
from framework.core.myexception import FuzzException

class dictionary:
	def __init__(self, payload, encoders_list):
	    self.__payload = payload
	    self.__encoders = encoders_list
	    self.__generator = self._gen() if self.__encoders else None

	def count (self):
	    return (self.__payload.count() * len(self.__encoders)) if self.__encoders else self.__payload.count()

	def __iter__(self):
	    return self

	def _gen(self):
	    while 1:
		pl = self.__payload.next()

		for name in self.__encoders:
		    if name.find('@') > 0:
			string = pl
			for i in reversed(name.split("@")):
			    string = Facade().get_encoder(i).encode(string)
			yield string
		    else:
			l = Facade().proxy("encoders").get_plugins(name)
			if not l:
			    raise FuzzException(FuzzException.FATAL, name + " encoder does not exists (-e encodings for a list of available encoders)")

			for e in l:
			    yield e().encode(pl)

	def next(self):
	    return self.__generator.next() if self.__encoders else self.__payload.next()

class requestGenerator:
	def __init__(self, seed_options, payload_options):
	    self.payload_options = payload_options
	    self.seed_options = seed_options
	    self.seed = FuzzRequest.from_options(seed_options, payload_options)
	    self._baseline = FuzzRequest.from_baseline(self.seed)
	    self.dictio = self._init_dictio(payload_options)

	    self.stats = FuzzStats.from_requestGenerator(self)

	    self._allvar_gen = None
	    if self.seed.wf_allvars is not None:
		self._allvar_gen = self.__allvars_gen(self.dictio)

	def _init_dictio(self, payload_options):
	    selected_dic = []

	    for name, params, extra, encoders in payload_options['payloads']:
		p = Facade().get_payload(name)(params, extra)
		selected_dic.append(dictionary(p, encoders) if encoders else p)

	    if len(selected_dic) == 1:
		return selected_dic[0]
	    elif payload_options["iterator"]:
		return Facade().get_iterator(payload_options["iterator"])(*selected_dic)
	    else:
		return Facade().get_iterator("product")(*selected_dic)

	def stop(self):
	    self.stats.cancelled = True

	def restart(self, seed):
	    self.seed = seed
	    self.dictio = self._init_dictio(self.payload_options)

	def count(self):
	    v = self.dictio.count()
	    if self.seed.wf_allvars is not None:
		v *= len(self.seed.wf_allvars_set)

	    if self._baseline: v += 1

	    return v

	def __iter__(self):
	    return self

	def __allvars_gen(self, dic):
	    for payload in dic:
		for r in FuzzRequest.from_all_fuzz_request(self.seed, payload):
		    yield r

	def next(self):
	    if self._baseline and self.stats.processed == 0 and self.stats.pending_seeds <= 1:
		return self._baseline

	    if self.stats.cancelled:
		raise StopIteration

	    if self.seed.wf_allvars is not None:
		return self._allvar_gen.next()
	    else:
		n = self.dictio.next()
		return FuzzRequest.from_seed(self.seed, n if isinstance(n, tuple) else (n,))
