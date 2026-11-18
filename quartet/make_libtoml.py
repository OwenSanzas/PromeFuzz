#!/usr/bin/env python3
"""Write PromeFuzz's lib.toml and config.toml for one case, by fixed rules.

usage: make_libtoml.py <case.json> <case_dir>

Rules (the same for every case):
- language: the language the build compiles the harness as (clang++ -> c++).
  The driver is later built at the gold's path by the project's own build
  script, so it must be in that language.
- driver_build_args: from the logged OSS-Fuzz build.  Compile flags
  (-I/-isystem/-iquote/-D/-U/-include/-std) from the call that compiled the
  harness; link inputs and flags from the call that writes the fuzzer (minus
  the harness, -o, and flags PromeFuzz adds itself: -fsanitize, -g, -O*), every
  file made absolute, an object make deleted as intermediate replaced by its
  source; plus the include root of each target header.
- compile_commands_path: Bear's database of that build.
- header_paths: the directories holding the headers that declare the
  project's dataset targets (field target_header), searched under /src; one
  lib.toml per library, as upstream.
- document_paths: README* files with a suffix PromeFuzz reads, and doc/ docs/
  directories, at the top of the upstream tree; document_has_api_usage = false.
- consumer_case_paths: test/ tests/ example/ examples/ at the top of the upstream
  tree (used only by PromeFuzz's scheduler, not in given mode).
- output_path: a fresh directory per case.
config.toml: upstream template; every LLM role uses Claude Sonnet 5 (no
sampling parameters), the embedding model is mxbai-embed-large (the paper's)
on a local Ollama.
"""
import json
import os
import re
import shlex
import sys

DOC_SUFFIX = ('.md', '.txt', '.html', '.htm', '.pdf', '.adoc', '.rst')
DROP_PREFIX = ('-fsanitize', '-fno-sanitize', '-O', '-fcoverage', '-fprofile')
DROP_EXACT = {'-g', '-c', '-gline-tables-only'}


def absolutize(arg, cwd):
  for flag in ('-I', '-L', '-include'):
    if arg.startswith(flag) and len(arg) > len(flag):
      p = arg[len(flag):]
      return flag + (p if os.path.isabs(p) else os.path.normpath(os.path.join(cwd, p)))
  if not arg.startswith('-') and re.search(r'\.(a|o|so[.0-9]*|la|lo)$', arg):
    return arg if os.path.isabs(arg) else os.path.normpath(os.path.join(cwd, arg))
  return arg


def same_file(arg, cwd, paths):
  if arg.startswith('-'):
    return False
  a = arg if os.path.isabs(arg) else os.path.join(cwd, arg)
  return os.path.realpath(a) in {os.path.realpath(p) for p in paths}


def main(case_json, d):
  case = json.load(open(case_json))
  # The harness file before the build (stub) and where the build compiles it.
  gold = (case['stub_path'], case['gold_path'])
  fuzzer = case['fuzzer_name']
  calls = [json.loads(l) for l in open(f'{d}/logs/cc.jsonl')]
  # The gold's link: the call writing /out/<fuzzer>; if the build links it
  # elsewhere and copies it to $OUT (flac, flatbuffers), the call writing a
  # file of that name.
  link, link_named = None, None
  for c in calls:
    argv = c['argv']
    if '-o' in argv and '-c' not in argv:
      out = argv[argv.index('-o') + 1]
      outp = os.path.normpath(out if os.path.isabs(out) else os.path.join(c['cwd'], out))
      if outp == os.path.join('/out', fuzzer):
        link = c
      elif os.path.basename(outp) == fuzzer:
        link_named = c
  link = link or link_named
  if link is None:
    sys.exit(f'no compiler call writes /out/{fuzzer}')
  # The call that compiled the harness: a separate `-c` whose object the link
  # uses, or else the link itself (compile and link in one call).
  def abspath(a, cwd):
    return a if os.path.isabs(a) else os.path.normpath(os.path.join(cwd, a))

  link_files = {abspath(a, link['cwd']) for a in link['argv'][1:] if not a.startswith('-')}
  harness_objs, hcall = set(), link
  for c in calls:
    argv = c['argv']
    if '-c' not in argv or '-o' not in argv:
      continue
    if not any(same_file(a, c['cwd'], gold) for a in argv):
      continue
    o = abspath(argv[argv.index('-o') + 1], c['cwd'])
    if o in link_files:
      harness_objs.add(o)
      hcall = c

  # Compile flags come from the harness's compile call only.
  comp_flags, it = [], iter(hcall['argv'][1:])
  for a in it:
    if a in ('-I', '-isystem', '-iquote'):
      comp_flags.append(a + abspath(next(it, ''), hcall['cwd']))
    elif a in ('-D', '-U', '-include'):
      v = next(it, '')
      # -include resolves like #include: keep it as written unless it names a
      # file relative to the call's directory.
      if a == '-include' and os.path.exists(os.path.join(hcall['cwd'], v)):
        v = abspath(v, hcall['cwd'])
      comp_flags += [a, v]
    elif a.startswith(('-I', '-isystem', '-iquote')):
      flag = next(f for f in ('-isystem', '-iquote', '-I') if a.startswith(f))
      comp_flags.append(flag + abspath(a[len(flag):], hcall['cwd']))
    elif a.startswith(('-D', '-U', '-std=')):
      comp_flags.append(a)
  # Link inputs and flags come from the link call: every file argument made
  # absolute; an object make deleted as an intermediate is replaced by its
  # source (lz4).  -std/-x belong to compiling the harness, not to linking.
  args, it = [], iter(link['argv'][1:])
  for a in it:
    if a == '-o':
      next(it, None)
      continue
    if a in ('-I', '-isystem', '-iquote', '-D', '-U', '-include', '-x'):
      next(it, None)
      continue
    if a in DROP_EXACT or a.startswith(DROP_PREFIX) or \
        a.startswith(('-I', '-isystem', '-iquote', '-D', '-U', '-std=', '-x')):
      continue
    if same_file(a, link['cwd'], gold):
      continue
    if a.startswith('-L'):
      args.append('-L' + abspath(a[2:], link['cwd']))
      continue
    if not a.startswith('-'):
      a = abspath(a, link['cwd'])
      if a in harness_objs:
        continue
      if not os.path.exists(a) and a.endswith('.o'):
        stem = a[:-2]
        src = next((stem + e for e in ('.c', '.cc', '.cpp', '.cxx') if os.path.exists(stem + e)), None)
        if src:
          a = src
    args.append(a)
  build_args = list(dict.fromkeys(comp_flags)) + args

  up = case['upstream_path']

  def header_dir(hdr):
    found = []
    for root, dirs, files in os.walk('/src'):
      dirs[:] = [x for x in dirs if x != '.git']
      for f in files:
        p = os.path.join(root, f)
        if p.endswith('/' + hdr):
          found.append(p)
    # Prefer the source tree's header over a copy generated into a build
    # output directory (janet: build/janet.h vs src/include/janet.h).
    found.sort(key=lambda p: (not p.startswith(up + '/'),
                              bool(re.search(r'/(build|out|_build)/', p)), len(p)))
    if not found:
      # The installed path may differ from the source layout: match the name.
      base = os.path.basename(hdr)
      for root, dirs, files in os.walk(up):
        dirs[:] = [x for x in dirs if x != '.git']
        if base in files:
          found.append(os.path.join(root, base))
      found.sort(key=len)
    if not found:
      sys.exit(f'declaring header {hdr} not found under /src')
    print('header', hdr, '->', found[:3])
    # The real path: a symlinked header tree (boost/boost -> libs/*/include)
    # makes PromeFuzz's relative_to() fail on the declaring file.
    return os.path.dirname(os.path.realpath(found[0]))

  header_dirs = sorted({header_dir(h) for h in case['project_target_headers']})
  # The include root each target header is written against (woff2/decode.h ->
  # /src/woff2/include), so a driver can include it the way the API documents.
  roots = []
  for h in case['project_target_headers']:
    for hd in header_dirs:
      cand = os.path.join(hd, os.path.basename(h))
      if cand.endswith('/' + h):
        roots.append('-I' + cand[:-len(h) - 1])
  # The project root too: source-tree headers include project-relative paths
  # (sentencepiece: src/*.h -> third_party/absl/...), which the gold, built
  # against the installed copies, does not need.
  roots.append('-I' + up)
  build_args = list(dict.fromkeys(roots)) + [a for a in build_args if a not in roots]

  docs = []
  if os.path.isdir(up):
    for f in sorted(os.listdir(up)):
      p = os.path.join(up, f)
      if os.path.isfile(p) and f.upper().startswith('README') and f.lower().endswith(DOC_SUFFIX):
        docs.append(p)
      if os.path.isdir(p) and f in ('doc', 'docs'):
        docs.append(p)
  consumers = [os.path.join(up, x) for x in ('test', 'tests', 'example', 'examples')
               if os.path.isdir(os.path.join(up, x))]
  # The language the build compiles the harness as (cjson compiles its .c
  # harness with clang++); the driver later takes the harness's place.
  lang = 'c++' if os.path.basename(hcall['argv'][0]).endswith('++') else 'c'

  def tl(v):
    return json.dumps(v)

  # PromeFuzz joins these into one command run by the shell: quote each
  # (libvips passes -DHWY_DISABLED_TARGETS=A|B, which the shell read as a pipe).
  shell_args = [shlex.quote(a) for a in build_args]
  name = re.sub(r'[^A-Za-z0-9_]', '_', case['oss_fuzz_project'])
  lib = (f'[{name}]\n'
         f'language = {tl(lang)}\n'
         f'compile_commands_path = {tl(d + "/compile_commands.json")}\n'
         f'header_paths = {tl(header_dirs)}\n'
         f'document_paths = {tl(docs)}\n'
         f'document_has_api_usage = false\n'
         f'output_path = {tl(d + "/out")}\n'
         f'driver_build_args = {tl(shell_args)}\n'
         f'consumer_case_paths = {tl(consumers)}\n'
         f'consumer_build_args = {tl(shell_args)}\n')
  open(f'{d}/lib.toml', 'w').write(lib)

  cfg = open('/tmp/promefuzz/config.template.toml').read()
  cfg = re.sub(r'(?m)^default_llm\s*=.*$', 'default_llm = "claude_sonnet_5"', cfg, count=1)
  cfg = re.sub(r'(?ms)^\[llm\.embedding_llm\].*?(?=^\[)',
               '[llm.embedding_llm]\nllm_type = "ollama"\nhost = "127.0.0.1"\n'
               'port = 11434\nmodel = "mxbai-embed-large"\n\n', cfg, count=1)
  cfg += ('\n[llm.claude_sonnet_5]\nllm_type = "anthropic"\n'
          'model = "claude-sonnet-5"\nmax_tokens = -1\ntimeout = 80\nretry_times = 3\n')
  open(f'{d}/config.toml', 'w').write(cfg)
  print(lib)


if __name__ == '__main__':
  main(sys.argv[1], sys.argv[2])
