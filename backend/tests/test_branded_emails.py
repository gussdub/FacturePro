"""Courriels transactionnels de marque (gabarit _brand_email).

Ces tests exercent les VRAIES fonctions d'envoi (resend monkeypatché), pas seulement le
gabarit : `_send_*_email` avale toute exception (`except Exception -> return False`), donc une
NameError ou un f-string cassé y serait TOTALEMENT silencieux en prod. Le test le plus important
est donc « la fonction retourne True ET le payload capturé contient bien le html + le texte ».
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import server  # noqa: E402


@pytest.fixture
def sent(monkeypatch):
    """Capture les payloads passés à resend.Emails.send au lieu d'envoyer."""
    box = []
    monkeypatch.setattr(server.resend.Emails, "send", lambda params: box.append(params) or {"id": "x"})
    monkeypatch.setattr(server, "RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    return box


# --------------------------------------------------------------------- gabarit
class TestBrandEmailTemplate:
    def test_contraintes_clients_de_messagerie(self):
        """Pas d'image distante (bloquée par défaut), pas de SVG inline (Gmail le retire),
        pas de flex/grid (Outlook ne les rend pas) : la marque doit tenir en HTML/table pur."""
        html, _ = server._brand_email("Titre", ["<strong>corps</strong>"])
        assert "<img" not in html
        assert "<svg" not in html
        assert "url(" not in html
        assert "display:flex" not in html and "display:grid" not in html
        assert "<table" in html

    def test_marque_et_liens_legaux(self):
        html, text = server._brand_email("Titre", ["corps"])
        assert "FacturePro" in html and "FacturePro" in text
        for url in ("https://facturepro.ca/privacy", "https://facturepro.ca/cgu"):
            assert url in html and url in text

    def test_version_texte_depouille_le_balisage(self):
        _, text = server._brand_email("Titre", ["Bonjour <strong>Ana</strong>"],
                                      footer_note="Note <em>x</em>")
        assert "Bonjour Ana" in text
        assert "<strong>" not in text and "<em>" not in text
        assert "Titre" in text and "Note x" in text

    def test_version_texte_decode_aussi_le_heading(self):
        """Le heading était le SEUL champ à ne pas passer par le dépouillement : la version
        texte recrachait son balisage brut, exactement le défaut corrigé pour les paragraphes."""
        _, text = server._brand_email("Chez <strong>Tremblay &amp; Fils</strong>", ["p"])
        assert text.splitlines()[0] == "Chez Tremblay & Fils"

    def test_version_texte_decode_les_entites(self):
        """Les paragraphes arrivent DEJA echappes (le HTML l'exige). Sans decodage, un nom
        d'entreprise comme « Tremblay & Fils » s'afficherait « Tremblay &amp; Fils » chez un
        destinataire en texte seul."""
        _, text = server._brand_email("T", ["Bienvenue chez <strong>Tremblay &amp; Fils</strong>"])
        assert "Tremblay & Fils" in text
        assert "&amp;" not in text

    def test_version_texte_garde_le_contenu_echappe_legitime(self):
        """L'ordre importe : retirer les balises AVANT de decoder. Decoder d'abord
        transformerait « &lt;b&gt; » (du contenu voulu) en balise, qui serait supprimee."""
        _, text = server._brand_email("T", ["Tapez &lt;b&gt; pour du gras"])
        assert "Tapez <b> pour du gras" in text

    def test_version_texte_coupe_les_br(self):
        _, text = server._brand_email("T", ["p"], footer_note="Copiez ce lien :<br>https://x.test")
        assert "Copiez ce lien :\nhttps://x.test" in text

    def test_version_texte_separe_les_paragraphes(self):
        """Sans ligne vide, les paragraphes se collent en un bloc illisible."""
        _, text = server._brand_email("T", ["Un", "Deux", "Trois"])
        assert "Un\n\nDeux\n\nTrois" in text

    def test_code_echappe_en_html_mais_brut_en_texte(self):
        """Un jeton reste une DONNÉE : jamais injecté brut dans le markup. En texte seul il
        doit rester copiable tel quel (pas d'entités HTML à retaper)."""
        raw = '<script>alert(1)</script>&"'
        html, text = server._brand_email("T", ["p"], code=raw)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert raw in text

    def test_bouton_echappe_libelle_et_url(self):
        html, text = server._brand_email(
            "T", ["p"], button=('Cliquez <ici> & "maintenant"', 'https://x.test/?a=1&b="2"'))
        assert "<ici>" not in html
        assert "&lt;ici&gt;" in html
        assert '&amp;b=&quot;2&quot;' in html      # quote=True : l'URL est dans un attribut
        assert 'https://x.test/?a=1&b="2"' in text  # le texte porte l'URL utilisable

    @staticmethod
    def _button_tag(html):
        """La balise <a> du bouton, et elle seule. Indispensable : `"#FFFFFF" in html` est
        TAUTOLOGIQUE (la bande d'en-tête en contient déjà), donc une assertion globale ne
        peut pas détecter un bouton dont la couleur de texte aurait changé."""
        import re
        m = re.search(r'bgcolor="%s"[^>]*>\s*(<a [^>]*>)' % server._BRAND_TEAL_DARK, html, re.S)
        assert m, "bouton introuvable : aucune cellule bgcolor teal foncé suivie d'un <a>"
        return m.group(1)

    def test_bouton_contraste_conforme(self):
        """Blanc sur #00A08C = 3,28:1 -> ÉCHOUE le seuil 4,5:1 d'un libellé de bouton.
        Le gabarit doit utiliser #00796B (5,32:1). Assertions portées sur la balise DU BOUTON."""
        html, _ = server._brand_email("T", ["p"], button=("Go", "https://x.test"))
        tag = self._button_tag(html)
        assert "color:#FFFFFF" in tag, f"texte du bouton pas blanc : {tag}"
        assert f"background:{server._BRAND_TEAL_DARK}" in tag, f"fond du bouton non conforme : {tag}"
        assert server._BRAND_TEAL not in tag.replace(server._BRAND_TEAL_DARK, ""), \
            "le bouton utilise le teal clair (3,28:1) quelque part"

    def test_bouton_pastille_entierement_cliquable(self):
        """RÉGRESSION MESURÉE : avec le padding sur le <td>, la cible tombait à 148x18 alors que
        la pastille visible faisait 200x45 — les 4 bords étaient morts DANS TOUS LES CLIENTS,
        car un <td> n'est pas un lien. La bordure, elle, fait partie de la boîte du <a> : elle
        est cliquable, et Outlook l'honore sur un inline. L'invariant testable est donc : ce qui
        fabrique la pastille doit vivre sur le <a>, jamais sur le <td>."""
        import re
        html, _ = server._brand_email("T", ["p"], button=("Go", "https://x.test"))
        tag = self._button_tag(html)
        assert "border:13px solid" in tag and "border-left-width:26px" in tag, \
            f"la pastille n'est pas faite de bordures sur le <a> : {tag}"
        cell = re.search(r'(<td align="center" bgcolor="%s"[^>]*>)' % server._BRAND_TEAL_DARK,
                         html).group(1)
        assert "padding" not in cell, \
            f"padding sur le <td> : la zone cliquable retombe à la boîte du texte -> {cell}"

    def test_sections_optionnelles_absentes_par_defaut(self):
        html, text = server._brand_email("T", ["p"])
        assert "word-break:break-all" not in html   # pas de bloc code
        assert "border-radius:10px" not in html     # pas de bouton
        assert text.count("\n\n") >= 1


# ----------------------------------------------------- vraies fonctions d'envoi
class TestPasswordResetEmail:
    def test_envoi_reel_produit_html_et_texte(self, sent):
        token = "Xq7_aB3cD9eF-gH1iJ2kL4mN5oP6qR8sT0uV"
        assert server._send_password_reset_email("a@b.test", token) is True
        assert len(sent) == 1
        p = sent[0]
        assert p["to"] == ["a@b.test"]
        assert "FacturePro" in p["html"]
        assert token in p["html"] and token in p["text"]
        assert "https://facturepro.ca/privacy" in p["html"]

    def test_sans_cle_api_aucun_envoi(self, monkeypatch):
        box = []
        monkeypatch.setattr(server.resend.Emails, "send", lambda params: box.append(params))
        monkeypatch.setattr(server, "RESEND_API_KEY", "")
        assert server._send_password_reset_email("a@b.test", "tok") is False
        assert box == []


class TestInvitationEmail:
    def test_nom_org_echappe_dans_le_corps_brut_dans_le_sujet(self, sent):
        """company_name est saisi par l'utilisateur. Dans le HTML il doit être échappé ;
        dans le SUJET (texte pur) il doit rester lisible, pas « &amp; »."""
        assert server._send_invitation_email(
            "a@b.test", 'Tremblay & Fils <script>alert(1)</script>', "tok123") is True
        p = sent[0]
        assert "<script>" not in p["html"]
        assert "Tremblay &amp; Fils" in p["html"]
        assert "Tremblay & Fils" in p["subject"]
        assert "&amp;" not in p["subject"]

    def test_bouton_et_lien_de_repli(self, sent):
        assert server._send_invitation_email("a@b.test", "Org", "tok123") is True
        p = sent[0]
        assert "accept-invite?token=tok123" in p["html"]
        assert "Accepter l'invitation" in p["html"]
        assert "accept-invite?token=tok123" in p["text"]   # utilisable en texte seul
        assert server._BRAND_TEAL_DARK in p["html"]


# --------------------------------------------------- les deux crons (sites non couverts)
# Ces deux endpoints construisent le courriel a l'INTERIEUR d'un try/except par organisation
# qui fait `continue`. Une NameError y est donc invisible : le cron renvoie {"notified": 0}
# — indiscernable d'un cron sain — et comme l'etat n'est ecrit qu'APRES un envoi reussi, il
# retente indefiniment sans alerter personne. D'ou ces tests, qui asservissent le PAYLOAD.
class _FakeColl:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.inserted = []
        self.updated = []

    def find(self, *a, **k):
        return iter(list(self.docs))

    def find_one(self, flt=None, *a, **k):
        for d in self.docs:
            if all(d.get(key) == val for key, val in (flt or {}).items()):
                return d
        return None

    def insert_one(self, doc):
        self.inserted.append(doc)

    def update_one(self, flt, upd, **k):
        self.updated.append((flt, upd))


class _FakeDB:
    def __init__(self, **colls):
        self._c = colls

    def __getattr__(self, name):
        return self._c.setdefault(name, _FakeColl())


@pytest.fixture
def request_stub():
    from starlette.requests import Request
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [],
                    "query_string": b"", "client": ("127.0.0.1", 0)})


class TestTrialExpiryCronEmail:
    def test_payload_de_marque_et_nom_echappe(self, sent, monkeypatch, request_stub):
        import asyncio
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        org = {"id": "org1", "subscription_status": "trial", "owner_id": "u1",
               "trial_ends_at": (now + timedelta(days=2)).isoformat()}
        owner = {"id": "u1", "email": "a@b.test", "company_name": 'Tremblay & Fils <b>'}
        monkeypatch.setattr(server, "db", _FakeDB(
            organizations=_FakeColl([org]), users=_FakeColl([owner]),
            trial_notifications=_FakeColl()))
        monkeypatch.setattr(server, "EXEMPT_USERS", set())

        res = asyncio.run(server.check_trial_expiry(request_stub))

        assert res["notified"] == 1, f"le cron n'a envoye aucun courriel : {res}"
        p = sent[0]
        assert p["html"] and p["text"]
        assert "FacturePro" in p["html"]
        # Le nom d'entreprise est saisi par l'utilisateur : echappe en HTML, lisible en texte.
        assert "<b>" not in p["html"]
        assert "Tremblay &amp; Fils" in p["html"]
        assert "Tremblay & Fils" in p["text"]
        assert "S'abonner maintenant" in p["html"]
        assert server._BRAND_TEAL_DARK in p["html"]


class TestMileageRateCronEmail:
    def test_payload_de_marque(self, sent, monkeypatch, request_stub):
        import asyncio
        # Force l'annee courante a etre "sans taux connu" pour atteindre le chemin d'envoi.
        monkeypatch.setattr(server, "_mileage_rate_for_year", lambda y: None)
        monkeypatch.setattr(server, "db", _FakeDB(
            organizations=_FakeColl([{"id": "org1", "owner_id": "u1"}]),
            users=_FakeColl([{"id": "u1", "email": "a@b.test"}]),
            mileage_rate_reminders=_FakeColl()))

        res = asyncio.run(server.check_mileage_rate_update(request_stub))

        assert res.get("count") == 1, f"le cron n'a envoye aucun courriel : {res}"
        p = sent[0]
        assert p["html"] and p["text"]
        assert "FacturePro" in p["html"]
        assert "allocation automobile" in p["html"]
        assert "https://facturepro.ca/privacy" in p["html"]


# ------------------------------------------------- integrite du balisage (toutes les variantes)
class TestMarkupIntegrity:
    """Le gabarit a 8 variantes (code / bouton / note, présents ou non) et contient des
    commentaires conditionnels MSO. Un commentaire ouvert sans fermeture avalerait tout le reste
    du courriel dans Outlook ; une balise non fermée casserait le rendu. Comme les fonctions
    d'envoi avalent les exceptions, rien de tout ça ne se verrait en prod : d'où ce test."""

    VARIANTS = [
        (code, button, note)
        for code in (None, "TOK-123")
        for button in (None, ("Go", "https://x.test/?a=1&b=2"))
        for note in (None, "Note <strong>x</strong>")
    ]

    @staticmethod
    def _parse(html):
        from html.parser import HTMLParser

        class _P(HTMLParser):
            VOID = {"meta", "br", "img", "hr", "input", "link"}

            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.stack, self.errors = [], []

            def handle_starttag(self, tag, attrs):
                if tag not in self.VOID:
                    self.stack.append(tag)

            def handle_endtag(self, tag):
                if tag in self.VOID:
                    return
                if not self.stack:
                    self.errors.append(f"</{tag}> orphelin")
                elif self.stack[-1] != tag:
                    self.errors.append(f"</{tag}> alors que {self.stack[-1]} est ouvert")
                    if tag in self.stack:
                        while self.stack and self.stack.pop() != tag:
                            pass
                else:
                    self.stack.pop()

        p = _P()
        p.feed(html)
        p.close()
        return p

    @pytest.mark.parametrize("code,button,note", VARIANTS)
    def test_balisage_bien_forme(self, code, button, note):
        html, _ = server._brand_email(
            "Titre <strong>gras</strong>", ["Un &amp; deux", "<strong>Trois</strong>"],
            code=code, button=button, footer_note=note)
        p = self._parse(html)
        assert p.errors == [], f"balisage mal imbriqué : {p.errors}"
        assert p.stack == [], f"balises jamais fermées : {p.stack}"

    @pytest.mark.parametrize("code,button,note", VARIANTS)
    def test_conditionnels_mso_complets(self, code, button, note):
        """Exactement 2 blocs MSO complets (ghost table ouvrante + fermante) et AUCUN marqueur
        orphelin en dehors d'un bloc."""
        import re
        html, _ = server._brand_email("T", ["p"], code=code, button=button, footer_note=note)
        blocks = re.findall(r"<!--\[if mso\]>.*?<!\[endif\]-->", html, re.S)
        assert len(blocks) == 2, f"{len(blocks)} bloc(s) MSO au lieu de 2"
        residu = re.sub(r"<!--\[if mso\]>.*?<!\[endif\]-->", "", html, flags=re.S)
        assert "[if mso]" not in residu and "[endif]" not in residu, "marqueur MSO orphelin"
        assert blocks[0].endswith("<tr><td><![endif]-->")
        assert blocks[1].endswith("</td></tr></table><![endif]-->")

    def test_un_seul_h1_dans_une_cellule(self):
        """Hors commentaires : un seul titre de niveau 1, ouvert/fermé, directement dans un <td>."""
        import re
        html, _ = server._brand_email("Titre", ["p"])
        sans_comm = re.sub(r"<!--.*?-->", "", html, flags=re.S)
        assert sans_comm.count("<h1") == 1 and sans_comm.count("</h1>") == 1
        assert re.search(r"<td[^>]*>\s*<h1", sans_comm, re.S), "le h1 n'est pas dans une cellule"

    def test_pas_de_chevron_brut_dans_les_commentaires(self):
        """Un assainisseur naïf peut mal découper un commentaire contenant des chevrons ; et ça
        fausse les vérifications par grep (compter '<h1' attrapait le commentaire)."""
        import re
        html, _ = server._brand_email("T", ["p"], button=("Go", "https://x.test"))
        for c in re.findall(r"<!--(.*?)-->", html, re.S):
            if "[if mso]" in c or "[endif]" in c:
                continue                      # les conditionnels MSO contiennent du balisage, c'est voulu
            assert "<" not in c and ">" not in c, f"chevron brut dans un commentaire : {c[:80]!r}"


# ------------------------------------ non-regression des 7 correctifs de la revue adversariale
class TestReviewFixesStayFixed:
    """Un correctif sans test est un correctif qui reviendra. Une assertion par correctif,
    ancrée sur l'attribut concerné et non sur une chaîne incidente."""

    @pytest.fixture
    def full(self):
        html, text = server._brand_email(
            "Titre", ["p"], code="TOK", footer_note="note",
            button=("Go", "https://x.test"))
        return html

    def test_h1_avec_margin_zero(self, full):
        import re
        assert re.search(r'<h1 style="margin:0', full), "le h1 a perdu son margin:0"

    def test_lang_sur_la_table_externe(self, full):
        """Gmail/Outlook.com suppriment l'élément racine : lang doit AUSSI être sur la table."""
        assert '<table role="presentation" lang="fr"' in full
        assert '<html lang="fr">' in full

    def test_aria_hidden_sur_le_glyphe_et_le_separateur(self, full):
        assert full.count('aria-hidden="true"') == 2, \
            "il doit y en avoir exactement 2 : le glyphe du logo et le séparateur du pied"
        assert '<span aria-hidden="true">&nbsp;·&nbsp;</span>' in full

    def test_ghost_table_impose_600px_a_outlook(self, full):
        """La table réelle est fluide (width=100% + max-width) ; c'est la ghost table MSO qui
        donne à Outlook, qui ignore max-width, une largeur dure."""
        import re
        ghost = re.search(r'<!--\[if mso\]>(.*?)<!\[endif\]-->', full, re.S).group(1)
        assert 'width="600"' in ghost
        assert 'max-width:600px;width:100%' in full
        assert 'width="600"' not in re.sub(r'<!--\[if mso\]>.*?<!\[endif\]-->', '', full,
                                           flags=re.S), \
            "la table réelle ne doit plus porter width=600 (sinon elle n'est plus fluide)"

    def test_log_du_cron_essai_sans_adresse(self, monkeypatch, request_stub):
        """Le handler écrivait l'adresse du destinataire et le message d'exception complet :
        un échec global (quota Resend) déversait tout le lot d'adresses dans les logs."""
        import asyncio, io, contextlib
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        monkeypatch.setattr(server, "db", _FakeDB(
            organizations=_FakeColl([{"id": "org1", "subscription_status": "trial",
                                      "owner_id": "u-42",
                                      "trial_ends_at": (now + timedelta(days=2)).isoformat()}]),
            users=_FakeColl([{"id": "u-42", "email": "marie@clinique.qc.ca",
                              "company_name": "Clinique"}]),
            trial_notifications=_FakeColl()))
        monkeypatch.setattr(server, "EXEMPT_USERS", set())
        monkeypatch.setattr(server, "RESEND_API_KEY", "re_test")

        def boom(params):
            raise RuntimeError("quota exceeded for marie@clinique.qc.ca")
        monkeypatch.setattr(server.resend.Emails, "send", boom)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            asyncio.run(server.check_trial_expiry(request_stub))
        out = buf.getvalue()
        assert "marie@clinique.qc.ca" not in out, f"adresse fuitée dans les logs : {out!r}"
        assert "@" not in out, f"une adresse subsiste dans les logs : {out!r}"
        assert "user=u-42" in out, f"id interne absent, diagnostic impossible : {out!r}"
        assert "RuntimeError" in out
        # Étiquette neutre : le try couvre aussi le gabarit et l'insert Mongo.
        assert "Resend error" not in out, "étiquette trompeuse : le try ne couvre pas que Resend"
