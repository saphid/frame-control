"""Get games checks that need no headset or network.

Run: python3 -m unittest discover -s tests
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ui"))

import frame_store  # noqa: E402
import frame_steam  # noqa: E402
import test_server  # noqa: E402  (not `from … import`, or unittest runs ServerGuards twice)


class SteamRoutes(test_server.ServerGuards):
    """Reuses ServerGuards' server (unresolvable SSH alias); validation runs before any SSH."""

    def test_steam_input_validation(self):
        for body in ({"action": "install", "appid": "620; reboot"}, {"action": "install", "appid": ""},
                     {"action": "uninstall", "appid": "620"}, {"appid": "620"}):
            status, payload = self.post("/api/steam", body)
            self.assertEqual(status, 400, f"{body} -> {payload}")

    def test_search_needs_country(self):
        for view in ("search", "browse", "details"):
            for query in ("q=portal", "q=portal&cc=A", "q=portal&cc=AU1", "q=portal&cc=%27x"):
                status, _, _ = self.request("GET", f"/api/steam/{view}?{query}", headers={"X-Frame-UI": "1"})
                self.assertEqual(status, 400, query)

    def test_details_validate_id_before_network(self):
        import server
        for appid in ("", "12x", "620%3Breboot", "-1"):
            with mock.patch.object(frame_store, "_get") as get:
                with self.assertRaises(server.Failure) as error:
                    server.steam_search(f"appid={appid}&cc=AU", "details")
            self.assertEqual(error.exception.status, 400)
            get.assert_not_called()

    def test_browse_and_details_routes(self):
        import server
        for view, helper, query, expected in (("browse", "browse", "cc=AU", {"results": []}),
                ("details", "details", "appid=620&cc=AU", {"game": []})):
            with mock.patch.object(frame_store, helper, return_value=[]) as call:
                self.assertEqual(server.steam_search(query, view), expected)
            call.assert_called_once_with(*((620, "AU") if view == "details" else ("AU",)))

    def test_search_paging_and_filters_validate_before_network(self):
        import server
        for query in ("start=-1", "start=hello", "start=1000001", "type=exploit", "sort=compat", "vr=invalid", "start=%C2%B2",
                      "price=-1", "price=1000000", "price=NaN", "discount=true", "discount=2", "tag=19", "tags=action,puzzle", "tags=999999", "tags=19,,492", "tags=19,19", "tags=19,492,1664,1752,21978,4182", "hidef2p=true", "hidef2p=2", "hidef2p=1&hidef2p=0",
                      "specials=1", "tags=1664&tags=19", "price=free&price=10", "type=game&type=dlc"):
            with mock.patch.object(frame_store, "search") as search:
                with self.assertRaises(server.Failure) as error:
                    server.steam_search("q=title&cc=AU&" + query)
            self.assertEqual(error.exception.status, 400)
            search.assert_not_called()
        page = {"results": [], "total": 55, "start": 50}
        with mock.patch.object(frame_store, "search", return_value=page) as search:
            self.assertEqual(server.steam_search("q=title&cc=AU&start=50&type=game&sort=name"), page)
        search.assert_called_once_with("title", "AU", 50, "game", "name", "all", "any", False, "", False)
        with mock.patch.object(frame_store, "search", return_value=page) as search:
            server.steam_search("cc=AU&price=10&discount=1&tags=21978,1752&hidef2p=1&start=50")
        search.assert_called_once_with("", "AU", 50, "all", "relevance", "all", "10", True, "21978,1752", True)

    def test_steam_routes_need_custom_header(self):
        self.assertEqual(self.request("GET", "/api/steam/owned")[0], 403)
        self.assertEqual(self.request("GET", "/api/steam/search?q=x&cc=AU")[0], 403)
        self.assertEqual(self.request("GET", "/api/steam/browse?cc=AU")[0], 403)
        self.assertEqual(self.request("GET", "/api/steam/details?appid=620&cc=AU")[0], 403)
        self.assertEqual(self.request("POST", "/api/steam", {"action": "install", "appid": "620"})[0], 403)

    def test_pinned_trailer_player_is_served_as_javascript(self):
        status, headers, body = self.request("GET", "/steam-hls.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])
        self.assertIn(b"1.6.13", body)


# Don't rerun the inherited ServerGuards tests under this module.
for name in [n for n in dir(test_server.ServerGuards) if n.startswith("test_")]:
    setattr(SteamRoutes, name, None)


class FrameSteamHelper(unittest.TestCase):
    def test_bad_usage_prints_json_error(self):
        for args in ([], ["install"], ["install", "12x"], ["remove", "620"]):
            out = subprocess.run([sys.executable, str(ROOT / "ui" / "frame_steam.py"), *args],
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(out.returncode, 1, args)
            self.assertIn("error", json.loads(out.stdout), args)

    def test_installed_game_is_not_reinstalled(self):
        with mock.patch.object(frame_steam, "Page") as page, \
                mock.patch.object(frame_steam, "steam_url") as launch:
            page.return_value.eval.return_value = {"name": "Gravitas", "installed": True}
            self.assertEqual(frame_steam.install(1067310)["state"], "installed")
        launch.assert_not_called()

    def test_license_and_eula_wait_for_headset(self):
        # Seen during #26's free Gravitas install: state 3 is not permission
        # to click through the license. The same guard applies to an EULA.
        for state in (3, 8):
            with self.subTest(state=state), \
                    mock.patch.object(frame_steam, "Page") as page, \
                    mock.patch.object(frame_steam, "steam_url") as launch, \
                    mock.patch.object(frame_steam.time, "sleep"):
                page.return_value.eval.side_effect = [
                    None, {"app": 1067310, "state": state, "need": 1, "free": 100}]
                self.assertEqual(frame_steam.install(1067310)["state"], "headset")
                launch.assert_called_once_with("steam://install/1067310")
                self.assertNotIn(mock.call("SteamClient.Installs.ContinueInstall()"),
                                 page.return_value.eval.call_args_list)

    def test_insufficient_space_leaves_options_open(self):
        with mock.patch.object(frame_steam, "Page") as page, \
                mock.patch.object(frame_steam, "steam_url"), \
                mock.patch.object(frame_steam.time, "sleep"):
            page.return_value.eval.side_effect = [
                {"name": "Gravitas", "installed": False},
                {"app": 1067310, "state": 7, "need": 100, "free": 10}]
            self.assertEqual(frame_steam.install(1067310)["state"], "headset")
            self.assertNotIn(mock.call("SteamClient.Installs.ContinueInstall()"),
                             page.return_value.eval.call_args_list)


class HelperErrors(unittest.TestCase):
    def test_json_error_found_despite_ssh_stderr(self):
        import server
        noise = server.Failure("Warning: Permanently added 'frame' to the list of known hosts.")
        noise.stdout = '{"error": "Steam\'s UI isn\'t answering"}\n'
        with mock.patch.object(server, "ssh", side_effect=noise):
            with self.assertRaises(server.Failure) as cm:
                server.steam_frame("owned")
        self.assertEqual(str(cm.exception), "Steam's UI isn't answering")

    def test_other_failures_pass_through(self):
        import server
        with mock.patch.object(server, "ssh", side_effect=server.Failure("Timed out talking to frame")):
            with self.assertRaises(server.Failure) as cm:
                server.steam_frame("owned")
        self.assertEqual(str(cm.exception), "Timed out talking to frame")


class StoreSearch(unittest.TestCase):
    def setUp(self):
        frame_store._compat.clear()
        frame_store._details.clear()
        review_patch = mock.patch.object(frame_store, "_get_text", return_value="")
        self.review_page = review_patch.start()
        self.addCleanup(review_patch.stop)

    def page(self, rows=1, total=322, kind="app"):
        html = "".join(f'''<a class="search_result_row" href="https://store.steampowered.com/{kind}/{620+i}/Title/">
            <div class="search_capsule"><img src="https://cdn.example/{i}.jpg"></div>
            <span class="title">Title &amp; {i}</span><div class="search_released">2019</div>
            <span class="search_review_summary positive" data-tooltip-html="Very Positive&lt;br&gt;95% positive"></span>
            <div class="discount_pct">-25%</div><div class="discount_original_price">A$ 39.99</div><div class="discount_final_price">A$ 29.99</div></a>''' for i in range(rows))
        return {"success": 1, "results_html": html, "total_count": total}

    def test_full_search_pages_preserve_regional_text_without_per_result_details(self):
        with mock.patch.object(frame_store, "_get", return_value=self.page(50)) as get, \
                mock.patch.object(frame_store, "details") as details, \
                mock.patch.object(frame_store, "frame_rating", return_value=3):
            page = frame_store.search("beat saber", "AU", 50, "dlc", "price", "supported")
        self.assertEqual((len(page["results"]), page["total"], page["start"], page["has_more"]), (50, 322, 50, True))
        result = page["results"][0]
        self.assertEqual((result["name"], result["price_text"], result["type"], result["frame"]), ("Title & 0", "A$ 29.99", "dlc", 3))
        self.assertEqual(result["review_summary"], "Very Positive\n95% positive")
        self.assertEqual(result["discount_percent"], 25)
        details.assert_not_called()
        path, params = get.call_args.args
        self.assertEqual(path, "search/results/")
        self.assertEqual({k: params[k] for k in ("term", "cc", "start", "count", "category1", "sort_by", "vrsupport")},
                         {"term": "beat saber", "cc": "AU", "start": 50, "count": 50, "category1": "21", "sort_by": "Price_ASC", "vrsupport": "401,402"})

    def test_packages_are_counted_and_never_sent_to_app_compatibility_endpoint(self):
        with mock.patch.object(frame_store, "_get", return_value=self.page(kind="sub", total=1)), \
                mock.patch.object(frame_store, "frame_rating") as rating:
            page = frame_store.search("title", "AU")
        self.assertEqual(page["results"][0]["id"], "sub_620")
        self.assertFalse(page["has_more"])
        rating.assert_not_called()

    def test_unreadable_page_is_error_instead_of_fake_empty_results(self):
        for payload in ({"success": 1, "results_html": "<script>bad()</script>", "total_count": 4}, {},
                        {"success": 0, "results_html": "", "total_count": 0}):
            with mock.patch.object(frame_store, "_get", return_value=payload), self.assertRaises(ValueError):
                frame_store.search("title", "AU")

    def test_empty_or_exhausted_page_does_not_offer_more(self):
        for start, total in ((0, 0), (50, 1)):
            with mock.patch.object(frame_store, "_get", return_value=self.page(rows=0, total=total)):
                page = frame_store.search("title", "AU", start)
            self.assertEqual(page["results"], [])
            self.assertFalse(page["has_more"])
            self.assertEqual(page["total"], total)

    def test_free_class_is_authoritative_and_foreign_links_are_rejected(self):
        payload = self.page(total=1)
        payload["results_html"] = payload["results_html"].replace('class="discount_final_price"', 'class="discount_final_price free"') + \
            '<a class="search_result_row" href="https://evil.example/app/1/"><span class="title">Evil</span></a>'
        with mock.patch.object(frame_store, "_get", return_value=payload), mock.patch.object(frame_store, "frame_rating", return_value=0):
            result = frame_store.search("title", "AU")["results"]
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["free"])

    def test_rating_failure_is_unknown_and_not_cached(self):
        with mock.patch.object(frame_store, "_get", side_effect=OSError("offline")):
            self.assertEqual(frame_store.frame_rating(620), 0)
        self.assertNotIn(620, frame_store._compat)

    def test_malformed_rating_is_unknown(self):
        for payload in ({"results": []}, {"results": {"frame_resolved_category": {}}},
                        {"results": {"frame_resolved_category": 9}}):
            frame_store._compat.clear()
            with mock.patch.object(frame_store, "_get", return_value=payload):
                self.assertEqual(frame_store.frame_rating(620), 0, payload)

    def test_catalog_filters_run_on_steam_before_pagination_with_steam_totals(self):
        with mock.patch.object(frame_store, "_get", return_value=self.page(50, 132)) as get, \
                mock.patch.object(frame_store, "frame_rating", return_value=0):
            page = frame_store.search("   ", "AU", 50, price="10", discount=True, tags="1664,1752", hidef2p=True)
        self.assertEqual((page["start"], page["total"], len(page["results"]), page["has_more"]), (50, 132, 50, True))
        params = get.call_args.args[1]
        self.assertEqual({k: params[k] for k in ("term", "start", "maxprice", "specials", "tags", "hidef2p")},
                         {"term": "", "start": 50, "maxprice": "10", "specials": 1, "tags": "1664,1752", "hidef2p": 1})
        with mock.patch.object(frame_store, "_get", return_value=self.page(1, 1)) as get, \
                mock.patch.object(frame_store, "frame_rating", return_value=0):
            result = frame_store.search("portal", "AU", price="free")["results"][0]
        self.assertEqual(get.call_args.args[1]["maxprice"], "free")
        # The upstream filter can return a paid-looking offer: do not invent a free price.
        self.assertFalse(result["free"])
        self.assertEqual(result["price_text"], "A$ 29.99")

    def test_helper_rejects_unwhitelisted_filters_before_network(self):
        for opts in ({"price":"0;reboot"}, {"tags":"999999"}, {"tags":"19,,492"}, {"tags":"19,19"}, {"tags":"19,492,1664,1752,21978,4182"}, {"hidef2p":1}, {"discount":1}, {"start":True}):
            with mock.patch.object(frame_store, "_get") as get, self.assertRaises(ValueError):
                frame_store.search("title", "AU", **opts)
            get.assert_not_called()

    def test_tag_allowlists_match_ui_and_live_steam_evidence(self):
        import re
        html = (ROOT / "ui/index.html").read_text()
        ui_tags = json.loads(re.search(r"const STEAM_TAGS = (.*?);", html)[1])
        self.assertEqual(ui_tags, frame_store.SEARCH_TAGS)
        self.assertEqual(len(ui_tags), 40)
        evidence = json.loads((ROOT / "docs/evidence/steam-hill-climb/live-endpoints-pass4.json").read_text())
        self.assertEqual({key: evidence["live_tags"][key] for key in ui_tags}, ui_tags)
        self.assertEqual(int(re.search(r"const STEAM_TAG_LIMIT = (\d+);", html)[1]), frame_store.SEARCH_TAG_LIMIT)

    def test_tag_ids_and_hidef2p_are_strict_and_bounded_before_network(self):
        for tags in (None, [], 19, "19,", ",19", "19, 492", "１９", "019", "19&specials=1", "19," * 100):
            with self.subTest(tags=tags), mock.patch.object(frame_store, "_get") as get, self.assertRaises(ValueError):
                frame_store.search("title", "AU", tags=tags)
            get.assert_not_called()
        for tags in ("", "21978", "19,492,1664,1752,21978"):
            self.assertTrue(frame_store.valid_search_tags(tags))
        with mock.patch.object(frame_store, "_get", return_value=self.page(1, 1)) as get, \
                mock.patch.object(frame_store, "frame_rating", return_value=0):
            frame_store.search("title", "AU")
        self.assertNotIn("tags", get.call_args.args[1])
        self.assertNotIn("hidef2p", get.call_args.args[1])

    def test_detail_media_about_tags_and_dlc_preserve_only_real_data(self):
        data = {"name":"Title", "about_the_game":"<h2>About</h2><p>Long &amp; useful<br>description</p>",
                "dlc":[11,12,11], "movies":[
                    {"name":"Real trailer", "thumbnail":"https://cdn.example/poster.jpg", "hls_h264":"https://video.example/master.m3u8"},
                    {"name":"Legacy trailer", "mp4":{"480":"https://video.example/clip.mp4"}, "webm":{"480":"javascript:bad()"}}]}
        self.review_page.return_value = '<a class="app_tag"> VR </a><a class="app_tag">Rhythm &amp; Music</a><a class="app_tag">VR</a>'
        with mock.patch.object(frame_store, "_get", return_value={"7":{"success":True,"data":data}}):
            result = frame_store.details(7,"AU")
        self.assertEqual(result["dlc_count"], 2)
        self.assertEqual(result["tags"], ["VR", "Rhythm & Music"])
        self.assertIn("Long & useful\ndescription", result["about"])
        self.assertEqual(result["movies"][0]["sources"], [{"url":"https://video.example/master.m3u8", "type":"application/vnd.apple.mpegurl"}])
        self.assertEqual(len(result["movies"][1]["sources"]), 1)
        frame_store._details.clear()
        self.review_page.side_effect = OSError("offline")
        with mock.patch.object(frame_store, "_get", return_value={"7":{"success":True,"data":{"name":"Unavailable extras"}}}):
            result = frame_store.details(7,"AU")
        self.assertEqual((result["movies"],result["tags"],result["about"],result["dlc_count"]), ([],[],"",None))

    def test_live_metadata_distinguishes_dlc_and_caches_per_country(self):
        data = {"name": "Extra songs", "type": "dlc", "is_free": False,
                "short_description": "Requires the base game", "fullgame": {"appid": "620", "name": "Base"},
                "developers": ["Studio"], "price_overview": {"final": 299, "currency": "AUD"},
                "screenshots": [{"path_full": "https://example.org/shot.jpg"}]}
        with mock.patch.object(frame_store, "_get", return_value={"7": {"success": True, "data": data}}) as get:
            au = frame_store.details(7, "AU")
            self.assertEqual(au["type"], "dlc")
            self.assertFalse(au["free"])
            self.assertEqual(au["base_game"]["name"], "Base")
            self.assertEqual(au["price"]["final"], 299)
            self.assertEqual(au["screenshots"], ["https://example.org/shot.jpg"])
            au["name"] = "Client mutation"
            self.assertEqual(frame_store.details(7, "AU")["name"], "Extra songs")
            self.assertEqual(get.call_count, 1)
            frame_store.details(7, "US")
            self.assertEqual(get.call_count, 2)

    def test_reviews_and_requirements_are_genuine_plain_data_and_optional(self):
        data = {"name": "VR title", "pc_requirements": {"minimum": "<b>VR Support:</b> SteamVR<br>4 GB RAM"},
                "categories": [{"description": "VR Only"}], "screenshots": [{"path_full": "https://cdn.example/shot.jpg"}]}
        self.review_page.return_value = '''<a class="user_reviews_summary_row" data-tooltip-html="95% of the 100 reviews in your language are positive">
            <div class="subtitle column">English Reviews:</div><span class="game_review_summary">Very Positive</span></a>'''
        with mock.patch.object(frame_store, "_get", return_value={"7": {"success": True, "data": data}}):
            result = frame_store.details(7, "AU")
        self.assertEqual(result["requirements"]["minimum"], "VR Support: SteamVR\n4 GB RAM")
        self.assertEqual(result["review_summaries"], [{"label": "English Reviews:", "rating": "Very Positive", "description": "95% of the 100 reviews in your language are positive"}])
        self.assertEqual(result["categories"], ["VR Only"])
        frame_store._details.clear()
        self.review_page.side_effect = OSError("offline")
        with mock.patch.object(frame_store, "_get", return_value={"7": {"success": True, "data": data}}):
            result = frame_store.details(7, "AU")
        self.assertEqual(result["review_summaries"], [])
        self.assertEqual(result["screenshots"], ["https://cdn.example/shot.jpg"])

    def test_browse_uses_real_metadata_and_omits_unavailable_titles(self):
        def details(appid, cc):
            self.assertEqual(cc, "AU")
            if appid != frame_store.VR_STARTERS[0]:
                raise ValueError("Not available in region")
            return {"name": "Live Steam name", "type": "game", "price": None, "free": True}
        with mock.patch.object(frame_store, "details", side_effect=details), \
                mock.patch.object(frame_store, "frame_rating", return_value=3):
            result = frame_store.browse("AU")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Live Steam name")
        self.assertTrue(result[0]["free"])

    def test_unavailable_browse_is_an_error_with_retry_rather_than_empty_success(self):
        with mock.patch.object(frame_store, "details", side_effect=OSError("offline")), \
                mock.patch.object(frame_store, "frame_rating", return_value=0):
            with self.assertRaisesRegex(ValueError, "unavailable right now"):
                frame_store.browse("AU")

    @unittest.skipUnless(shutil.which("node"), "Node exercises production store functions")
    def test_store_ui_behavior(self):
        result = subprocess.run(["node", "--test", str(ROOT / "tests/steam_store.cjs")],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
