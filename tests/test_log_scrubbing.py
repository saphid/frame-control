"""Issue #81: synthetic, deterministic log scrubbing; no sockets or private data."""
import sandbox  # noqa: F401
import random
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ui'))
import frame_link as fl
import frame_telemetry as tm


def baseline(text, hosts):
    """Frozen v0.4.11 connection pipeline, before issue #81's extra spans.

    Keep these operations independent of frame_link's implementations so a change
    to its ordering or matching cannot silently weaken the differential oracle.
    The shared scrubber's default behavior is deliberately unchanged by this fix.
    """
    keep = {'host', 'hostname', 'to', 'port', 'answer', 'the', 'a', 'an', 'this',
            'it', 'its', 'be', 'connect', 'find', 'work', 'try'}
    names = sorted({h for h in hosts if h and h.lower() not in keep}, key=len, reverse=True)
    parts = re.split(r'(<(?:host|user|email|ip|mac|steamid|hex|token|ssh-key|pem|url|redacted)>)', text)
    for i in range(0, len(parts), 2):
        for name in names:
            parts[i] = re.sub(r'(?<![\w.:-])%s(?![\w-]|[:.%%]\w)' % re.escape(name),
                              '<host>', parts[i], flags=re.I)
    plain = keep - {'host', 'hostname', 'to', 'port'}

    def operand(match):
        word = match.group(2).rstrip('.')
        return (match.group(0) if word.lower() in plain else
                f'{match.group(1)} <host>{match.group(2)[len(word):]}')

    text = re.sub(r'''(?i)\b(hostname|host|to(?:\s+host)?)\s+(?!<)([^\s:,;'"()|]+)''',
                  operand, ''.join(parts))
    return tm.scrub(text, 600)


class LogScrubbing(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(tm, '_user_names', return_value={'SyntheticLogin'})
        patch.start()
        self.addCleanup(patch.stop)

    def test_display_name_crosses_a_scrubber_token(self):
        name = '<host> Jane Doe headset'
        self.assertEqual(fl.scrub_failure(name + ' stopped answering', [name]), '<host> stopped answering')
        self.assertEqual(fl.scrub_failure('<user>@<host>: <ip>', ['user', 'host', 'ip']),
                         '<user>@<host>: <ip>')
        self.assertEqual(fl.scrub_failure('<host>', ['<host>']), '<host>')

    def test_all_standalone_tokens_survive_and_whole_names_cross_them(self):
        for token in ('host', 'user', 'email', 'ip', 'mac', 'steamid', 'hex',
                      'token', 'ssh-key', 'pem', 'url', 'redacted'):
            token = '<' + token + '>'
            name = token + ' Synthetic Fixture headset'
            with self.subTest(token=token):
                self.assertEqual(fl.scrub_failure(token, [token, token[1:-1]]), token)
                self.assertEqual(fl.scrub_failure(name.upper() + ' failed', [name]), '<host> failed')

    def test_a_name_crossing_the_output_limit_leaves_no_fragment(self):
        name = '<host> ' + 'Synthetic ' * 100 + 'headset'
        self.assertEqual(fl.scrub_failure(name + ' trailing detail', [name]), '<host>')

    def test_display_name_cannot_swallow_ssh_operand_marker(self):
        text = 'ssh: connect to host bastion-jane port 22: Connection refused'
        self.assertEqual(fl.scrub_failure(text, ['to host']),
                         'ssh: connect <host> <host> port 22: Connection refused')

    def test_reverted_fix_counterexamples(self):
        cases = [
            ('Could not connect to hostname bastion-jane', ['connect to'], ['bastion-jane']),
            ('Jane Smith@<host>: Permission denied', ['Smith@<host>'], ['Jane', 'Smith']),
            ('frame.local Jane Doe headset stopped answering', ['frame.local Jane Doe headset'], ['Jane', 'Doe']),
            ('x ' * 295 + 'frame.local Jane Doe headset', ['frame.local Jane Doe headset'], ['Jane', 'Doe']),
            ('https://jane@example.com/private(confidential)', ['jane@example.com'], ['private', 'confidential']),
            (r'C:\Users\Jane@workpc (Smith)\.ssh\config', ['Jane@workpc'], ['Jane', 'Smith']),
            ('-----BEGIN PRIVATE KEY-----\nSYNTHETICBODY\n-----END PRIVATE KEY-----@frame',
             ['KEY-----@frame'], ['SYNTHETICBODY']),
            ('Could not connect to hostname /home/Jane Doe/.ssh/config', ['connect to'], ['Jane', 'Doe']),
        ]
        for text, hosts, private in cases:
            with self.subTest(text=text):
                out = fl.scrub_failure(text, hosts)
                for value in private:
                    self.assertNotIn(value, out)
                self.assertLessEqual(len(out), 600)

    def test_overlapping_names_and_operands_and_literal_tokens(self):
        cases = [
            ('Alpha Beta Gamma failed', ['Alpha Beta', 'Beta Gamma'], '<host> failed'),
            ('<host> Jane Doe headset failed', ['<host> Jane Doe headset', 'Jane Doe'], '<host> failed'),
            ('to hostname bastion-jane', [], 'to <host> <host>'),
            ('<host failed', ['<host'], '<host> <host>'),
        ]
        for text, hosts, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(fl.scrub_failure(text, hosts), expected)

    def test_randomized_differential_against_v0411(self):
        rng = random.Random(81)
        templates = [
            'https://{u}@example.invalid/{p}(confidential)?key={p}',
            r'C:\Users\{u}@workpc ({p})\.ssh\config',
            '/home/{u} {p}/.ssh/config',
            '-----BEGIN PRIVATE KEY-----\n{p}\n-----END PRIVATE KEY-----@frame',
            '{u}.{p}@example.invalid',
            'fe80::abcd%{u}',
            '{u} {p}@frame.local: Permission denied',
            'ssh-ed25519 {p}',
            'password={p}',
            '<host> {u} {p} headset stopped answering',
            'frame.local {u} {p} headset stopped answering',
        ]
        for iteration in range(1200):
            user = 'Synthetic' + ''.join(rng.choices('abcdefghijklmnopqrstuvxyz', k=14))
            private = 'Fixture' + ''.join(rng.choices('abcdefghijklmnopqrstuvxyz', k=18))
            field = rng.choice(templates).format(u=user, p=private)
            prefix = rng.choice(['', 'Could not connect to hostname ', 'ssh: connect to host ',
                                 'Timed out talking to ', 'debug | ', 'x ' * 295])
            text = prefix + field + rng.choice(['', ' port 22: refused', '\nnext line', "'s password: "])
            # Names intentionally cut through the syntax later scrubber rules need.
            options = [user, user + '@workpc', private, 'connect to', 'to host',
                       '<host> ' + user + ' ' + private + ' headset',
                       'frame.local ' + user + ' ' + private + ' headset',
                       'KEY-----@frame', 'host', '<host>', 'SyntheticLogin']
            hosts = rng.sample(options, rng.randrange(5))
            before, after = baseline(text, hosts), fl.scrub_failure(text, hosts)
            with self.subTest(iteration=iteration, text=text, hosts=hosts):
                trace = fl._ScrubTrace(text)
                traced = tm.scrub(fl.hide_operands(fl.hide_hosts(text, hosts, _trace=trace),
                                                  _sub=trace.sub), 600, _sub=trace.sub)
                self.assertEqual(traced, before)
                # Compare every original three-character window, not just whole
                # canaries: even a partially exposed user/path/secret is a regression.
                # Mask placeholders with a separator so removing one cannot join
                # unrelated text into a misleadingly new three-character window.
                old_visible = fl.PLACEHOLDER.sub('\0', before)
                new_visible = fl.PLACEHOLDER.sub('\0', after)
                for start in range(len(text) - 2):
                    fragment = text[start:start + 3]
                    if fragment not in old_visible:
                        self.assertNotIn(fragment, new_visible)
                self.assertLessEqual(len(after), 600)


if __name__ == '__main__':
    unittest.main()
