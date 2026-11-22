/* LeanLink web UI additions: local firmware upload with in-browser verification.
   Online updates from the vendor bucket are disabled because they would replace the patched firmware. */
var LL_KEY_HEX = "@@KEY@@";
var LL_LATEST = "@@LATEST@@";  /* GitHub page of the newest release */
var LL_ISSUES = "@@ISSUES@@";
var llAppver = "";

/* ---- Language: picked automatically from the browser, like the vendor page does with its language files.
   Dictionaries come from tools/webui/i18n/*.json and are inserted by the builder. ---- */
var LL_TR = @@I18N@@;
var LL_LANG = (function () {
	var l = String((navigator.languages && navigator.languages[0]) || navigator.language || "en").toLowerCase();
	if (/^sk/.test(l)) return LL_TR.sk ? "sk" : "cs";
	var two = l.slice(0, 2);
	return LL_TR[two] ? two : "en";
})();
function T(s, args) {
	var d = LL_TR[LL_LANG] || {}, e = LL_TR.en || {};
	var r = d[s] != null ? d[s] : (e[s] != null ? e[s] : s);
	if (args) for (var i = 0; i < args.length; i++) r = r.split("{" + i + "}").join(args[i]);
	return r;
}
function llI18nPage() {
	document.documentElement.lang = LL_LANG;
	var ids = { ll_sub: "Wireless Android Auto & CarPlay · debloated", ll_fwtitle: "Firmware update",
		ll_go: "Upload and install", ll_foot: "not affiliated with the vendor", txt9_ll: "Save problem report" };
	Object.keys(ids).forEach(function (id) { var e = document.getElementById(id); if (e) e.textContent = T(ids[id]); });
	/* Vendor section titles come from the box's own language file (no Czech there): translate the English ones. */
	var d = LL_TR[LL_LANG] || {};
	for (var i = 0; i < 22; i++) {
		var e = document.getElementById("txt" + i), k = e ? e.textContent.replace(/:$/, "").trim() : "";
		if (e && d[k]) e.textContent = d[k];
	}
	var t = document.getElementById("txt_desc"); if (t) t.placeholder = T("Please enter text here");
}
var llFile = null, llDevProject = null;

function llKey() {
	var k = new Uint8Array(256);
	for (var i = 0; i < 256; i++) k[i] = parseInt(LL_KEY_HEX.substr(i * 2, 2), 16);
	return k;
}

function llMd5(b) {
	var K = [], S = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21], i;
	for (i = 0; i < 64; i++) K[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 4294967296) | 0;
	var n = b.length, nb = ((n + 8) >>> 6) + 1, w = new Int32Array(nb * 16);
	for (i = 0; i < n; i++) w[i >> 2] |= b[i] << ((i % 4) * 8);
	w[n >> 2] |= 0x80 << ((n % 4) * 8);
	w[nb * 16 - 2] = (n * 8) | 0;
	w[nb * 16 - 1] = Math.floor(n / 536870912) | 0;
	var a0 = 0x67452301, b0 = 0xefcdab89 | 0, c0 = 0x98badcfe | 0, d0 = 0x10325476;
	for (var j = 0; j < w.length; j += 16) {
		var A = a0, B = b0, C = c0, D = d0, F, g;
		for (i = 0; i < 64; i++) {
			var r = i >> 4;
			if (r == 0) { F = (B & C) | (~B & D); g = i; }
			else if (r == 1) { F = (D & B) | (~D & C); g = (5 * i + 1) % 16; }
			else if (r == 2) { F = B ^ C ^ D; g = (3 * i + 5) % 16; }
			else { F = C ^ (B | ~D); g = (7 * i) % 16; }
			var s = S[r * 4 + (i % 4)], t = D;
			D = C; C = B;
			var x = (A + F + K[i] + w[j + g]) | 0;
			B = (B + ((x << s) | (x >>> (32 - s)))) | 0;
			A = t;
		}
		a0 = (a0 + A) | 0; b0 = (b0 + B) | 0; c0 = (c0 + C) | 0; d0 = (d0 + D) | 0;
	}
	var h = "";
	[a0, b0, c0, d0].forEach(function (v) {
		for (var k = 0; k < 4; k++) h += ("0" + ((v >>> (k * 8)) & 255).toString(16)).slice(-2);
	});
	return h;
}

/* Returns {ok, project, error, size} for an encrypted update.img (Uint8Array). */
function llVerify(enc) {
	var key = llKey(), d = new Uint8Array(enc.length);
	for (var i = 0; i < enc.length; i++) d[i] = enc[i] ^ key[i & 255];
	var head = String.fromCharCode.apply(null, d.subarray(0, 45));
	var m = /^([0-9a-f]{32})  update\.swu\n$/i.exec(head);
	if (!m) return { ok: false, error: T("not a firmware image for this platform (bad header)") };
	var body = d.subarray(45);
	var tail = String.fromCharCode.apply(null, body.subarray(Math.max(0, body.length - 2048)));
	if (tail.indexOf("TRAILER!!!") < 0) return { ok: false, error: T("image is truncated (no archive trailer)") };
	if (llMd5(body) != m[1].toLowerCase()) return { ok: false, error: T("checksum mismatch (corrupted download?)") };
	var meta = String.fromCharCode.apply(null, body.subarray(0, Math.min(body.length, 16384)));
	var p = /ly_project_name\s*=\s*"(ly\d+)"/.exec(meta);
	if (!p) return { ok: false, error: T("image does not declare a project") };
	return { ok: true, project: p[1], size: enc.length };
}

function llSet(id, html) { var e = document.getElementById(id); if (e) e.innerHTML = html; }
function llProg(v) { var e = document.getElementById("ll_prog"); if (e) e.style.width = (0 | v) + "%"; }
function llBtn(on) {
	var b = document.getElementById("ll_go");
	if (b) b.className = "weui-btn weui-btn_primary" + (on ? "" : " weui-btn_disabled");
}

function llInit(j) {
	var v = (j.sys && j.sys.appver) ? j.sys.appver : "";
	llAppver = v;
	llDevProject = "ly" + (v.split(".")[1] || "");
	llSet("ll_ver", v);
	llI18nPage();
llSet("ll_note", T("NOTE", [llDevProject]));
	llSettings(j);
	llOnline();
}

/* Settings with real meanings (decoded from raaservice / lylinkapp, see docs/SETTINGS.md).
   Most changes restart the box. */
var LL_SET = {
	led:   { row: "div_led", title: "Status LED", opts: ["On", "Off"],
		notes: ["The LED shows the connection state.", "The LED stays dark."],
		help: "Switches the light on the box off, e.g. if it is distracting at night." },
	delay: { row: "div_delay", title: "Start-up delay", opts: ["Off", "15 s", "30 s"],
		notes: ["The box starts right away (recommended).", "Bluetooth, Wi-Fi and USB start 15 s after power-on.", "Bluetooth, Wi-Fi and USB start 30 s after power-on."],
		help: "Wait before the box appears to the car. Use only if the car misses the adapter after starting the engine." },
	vid:   { row: "div_vid", title: "CarPlay video mode", opts: ["Standard", "Compatibility"],
		notes: ["Default CarPlay video.", "Vendor compatibility mode for CarPlay video; its exact behaviour is not documented."],
		help: "CarPlay only, no effect on Android Auto. Try Compatibility only if the CarPlay picture is broken on your head unit." },
	aud:   { row: "div_aud", title: "CarPlay audio after calls", opts: ["Standard", "Re-sync after calls"],
		notes: ["Default.", "After a call the box takes the car audio back, for cars where music stays silent after a call."],
		help: "CarPlay only. Re-sync takes the car audio back after a phone call if music stays silent." },
	gps:   { row: "div_gps", title: "CarPlay GPS source", opts: ["Car GPS", "Phone GPS only"],
		notes: ["CarPlay may use the car's GPS signal.", "CarPlay uses only the iPhone's own GPS (based on the firmware code, not verified in a car)."],
		help: "CarPlay only (Android Auto always uses the car GPS when the car has one). Choose phone GPS if the position in maps jumps." }
};
var LL_WIFI = [
	{ label: "36 \u00b7 5 GHz \u00b7 recommended (Europe)", value: 36 },
	{ label: "6 \u00b7 2.4 GHz \u00b7 older phones, longer range", value: 6 },
	{ label: "149 \u00b7 5 GHz \u00b7 USA / Asia", value: 149 },
	{ label: "161 \u00b7 5 GHz \u00b7 USA / Asia", value: 161 }
];

function llHelp(row, title, help) {
	var r = document.getElementById(row);
	if (!r) return;
	var bd = r.querySelector(".weui-cell__bd");
	if (!bd) return;
	var p = bd.querySelector("p");
	if (p) { p.removeAttribute("id"); p.textContent = T(title); }
	if (!bd.querySelector(".ll-help")) {
		var h = document.createElement("div");
		h.className = "ll-help";
		h.textContent = T(help);
		bd.appendChild(h);
	}
}

function llAsk(title, text, yes) {
	if (typeof weui != "undefined" && weui.confirm) {
		weui.confirm(text, { title: title, buttons: [
			{ label: T("Cancel"), type: "default", onClick: function () {} },
			{ label: T("Apply"), type: "primary", onClick: yes }] });
	} else { yes(); }
}

/* Option list: one tap or click picks an option (the vendor's picker is a scroll wheel that ignores taps).
   items: [{label, value}]; the option whose label matches the value shown in the row (#key) gets a check mark. */
function llMenu(key, items, onPick) {
	var e = document.getElementById(key), cur = e ? e.textContent.trim() : "";
	weui.actionSheet(items.map(function (it) {
		var on = cur && (it.label == cur || it.label.indexOf(cur + " ") == 0);
		return { label: (on ? "\u2713 " : "") + it.label, onClick: function () { onPick(it.value); } };
	}), [{ label: T("Cancel"), onClick: function () {} }]);
}

/* opts: labels; vals (optional): values sent to the box; notes (optional): what each option does */
function llPick(key, opts, vals, notes, title, restart) {
	llMenu(key, opts.map(function (l, i) { return { label: T(l), value: i }; }), function (i) {
		var v = vals ? vals[i] : i;
		var text = (notes && notes[i] ? T(notes[i]) + " " : "") + (restart === false ? "" : T("RESTART"));
		llAsk(T(title || "Change setting") + ": " + T(opts[i]), text, function () {
			llSet(key, restart === false ? T(opts[i]) : T("{0} · restarting…", [T(opts[i])]));
			fetch("/cgi-bin/index.cgi?id=set&" + key + "=" + v).then(function (r) { return r.json(); }).then(function (j) {
				llSet(key, j.code == 0 ? T(opts[i]) : T("failed ({0})", [j.code]));
			}).catch(function () { llSet(key, T(opts[i])); });
		});
	});
}

function llSettings(j) {
	Object.keys(LL_SET).forEach(function (key) {
		var c = LL_SET[key], r = document.getElementById(c.row);
		if (!r || r.style.display == "none" || (r.parentElement && r.parentElement.className == "hide")) return;
		llHelp(c.row, c.title, c.help);
		var v = parseInt(j[key], 10);
		llSet(key, T(c.opts[v >= 0 && v < c.opts.length ? v : 0]));
		r.removeAttribute("onclick");
		r.setAttribute("href", "javascript:;");
		r.onclick = function (e) { e.preventDefault(); llPick(key, c.opts, null, c.notes, c.title); };
	});
	llHelp("div_wif", "Wi-Fi channel", "Channel of the box's own Wi-Fi. Change it only if the phone connection drops; 5 GHz is faster, 2.4 GHz reaches further.");
	var w = document.getElementById("div_wif");
	if (w) {
		w.setAttribute("href", "javascript:;");
		w.onclick = function (e) {
			e.preventDefault();
			llMenu("wifi", LL_WIFI.map(function (o) { return { label: T(o.label), value: o.value }; }), function (ch) {
				llAsk(T("Wi-Fi channel {0}", [ch]), T("WIFI_CONFIRM", [ch]), function () {
					llSet("wifi", T("{0} · restarting Wi-Fi…", [ch]));
					fetch("/cgi-bin/index.cgi?id=set&wifi=" + ch).then(function (r) { return r.json(); })
						.then(function (k) { llSet("wifi", k.code == 0 ? String(ch) : T("failed ({0})", [k.code])); })
						.catch(function () { llSet("wifi", String(ch)); });
				});
			});
		};
	}
	/* Vendor reset (index.cgi): rst=1 forgets pairings and the start mode, rst=2 wipes /mnt/UDISK (also the
	   settings). The vendor picker offered only rst=1 and read its label from txt19, which llHelp removes. */
	llHelp("div_rst", "Restore factory settings", "Forget the paired phones only, or reset everything including the settings above. LeanLink stays installed.");
	var rs = document.getElementById("div_rst");
	if (rs) {
		rs.setAttribute("href", "javascript:;");
		rs.onclick = function (e) {
			e.preventDefault();
			llPick("rst", ["Forget phones", "Everything"], [1, 2], [
				"Forgets paired phones and the Android Auto / CarPlay start mode; the settings on this page stay. The box restarts; pair your phone again afterwards.",
				"Also resets the settings on this page to their defaults. LeanLink stays installed. The box restarts; pair your phone again afterwards."],
				"Restore factory settings", false);
		};
	}

	/* "aa" is the Android Auto certificate switch (the vendor labels it "Video streaming mode"). */
	var aa = document.getElementById("div_aa");
	if (aa && j.aa != null) {
		llHelp("div_aa", "Android Auto certificate", "Certificate the box uses for Android Auto. Switch to built-in only if Android Auto stops starting.");
		var lab = ["Cloud (default)", "Built-in"], val = [1, 0];
		llSet("aa", T((j.aa[0] == "2" || j.aa[0] == "x") ? lab[0] : lab[1]));
		aa.setAttribute("href", "javascript:;");
		aa.onclick = function (e) {
			e.preventDefault();
			llPick("aa", lab, val, ["Use the vendor's cloud certificate (normal).",
				"Use Google's reference certificate built into the firmware (valid until 2044)."], "Android Auto certificate");
		};
	}
	var ph = { txt_brand: "E.g. Volkswagen", txt_model: "E.g. Tiguan", txt_year: "E.g. 2018" };
	Object.keys(ph).forEach(function (id) { var e = document.getElementById(id); if (e) e.placeholder = T(ph[id]); });
}

/* No online check: a phone on the box Wi-Fi has no internet, so the page only links to the newest release. */
function llOnline() {
	llSet("ll_online", LL_LATEST.indexOf("http") == 0 ? T("LATEST", [LL_LATEST, llDevProject]) : "");
}

function llCheck(f) {
	llFile = null; llBtn(false); llProg(0);
	if (!f) return;
	llSet("ll_info", T("Checking {0} …", [f.name]));
	f.arrayBuffer().then(function (buf) { llCheckBuffer(buf, f.name); })
		.catch(function (e) { llSet("ll_info", '<span class="ll-bad">✕ ' + T("cannot read file: {0}", [e]) + "</span>"); });
}

function llCheckBuffer(buf, label) {
	llFile = null; llBtn(false); llProg(0);
	{
		var r = llVerify(new Uint8Array(buf));
		if (!r.ok) { llSet("ll_info", '<span class="ll-bad">✕ ' + r.error + "</span>"); return; }
		if (r.project != llDevProject) {
			llSet("ll_info", '<span class="ll-bad">✕ ' + T("image is for {0}, this box is {1}. Images are not interchangeable.", [r.project, llDevProject]) + "</span>");
			return;
		}
		llFile = buf;
		llSet("ll_info", '<span class="ll-ok">✓ ' + T("{0}: valid image for {1}, checksum OK, {2} MB",
			[label, r.project, (r.size / 1048576).toFixed(1)]) + "</span>");
		llBtn(true);
	}
}

function llPoll(t0) {
	fetch("/cgi-bin/index.cgi?id=host", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) {
		var el = (Date.now() - t0) / 1000;
		if (j.update == 3) {
			llProg(95); llSet("ll_sta", T("Written. Rebooting into the new firmware …"));
			fetch("/cgi-bin/index.cgi?id=set&conn=aoa").catch(function () {});
			setTimeout(function () { llProg(100); llSet("ll_sta", T("Done. The box restarts; rejoin its Wi-Fi in about 30 s.")); }, 3000);
			return;
		}
		if (j.update > 3) { llSet("ll_sta", '<span class="ll-bad">' + T("Update failed (state {0})", [j.update]) + "</span>"); llBtn(true); return; }
		llProg(30 + Math.min(60, el * 60 / 90));
		llSet("ll_sta", T("Writing to flash, do not unplug … {0} s", [0 | el]));
		setTimeout(function () { llPoll(t0); }, 2000);
	}).catch(function () { setTimeout(function () { llPoll(t0); }, 2000); });
}

function llFlash() {
	if (!llFile) return;
	llBtn(false);
	var xhr = new XMLHttpRequest(), fd = new FormData();
	fd.append("file", new Blob([llFile], { type: "application/octet-stream" }), "blob");
	xhr.upload.onprogress = function (e) { if (e.total) llProg(e.loaded * 30 / e.total); };
	xhr.onreadystatechange = function () {
		if (xhr.readyState != 4) return;
		if (xhr.status == 200 && /"code":\s*0/.test(xhr.responseText)) {
			llSet("ll_sta", T("Uploaded. Writing to flash …")); llPoll(Date.now());
		} else {
			llSet("ll_sta", '<span class="ll-bad">' + T("Upload rejected: {0}", [xhr.responseText || xhr.status]) + "</span>"); llBtn(true);
		}
	};
	llSet("ll_sta", T("Uploading …"));
	xhr.open("POST", "/cgi-bin/index.cgi?id=upload");
	xhr.send(fd);
}

/* Problem report: stays on this device / goes to the LeanLink issue tracker, never to the vendor cloud. */
function llRedact(t) {
	return t.replace(/\b([0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b/gi, function (m) { return m.slice(0, 9) + "xx:xx:xx"; })
		.replace(/("sn":\s*")([0-9a-f]{8})[0-9a-f]+/gi, "$1$2xxxxxxxxxxxxxxxxxxxxxxxx")
		.replace(/\b(MX\d|SS|SV|JH|DB|mac=)([0-9A-F]{6})[0-9A-F]{6}/gi, "$1$2XXXXXX")   /* MACs without separators */
		.replace(/\b([0-9A-F]{6})[0-9A-F]{6}\b/gi, "$1XXXXXX")
		.replace(/\b([0-9a-f]{8})[0-9a-f]{24}\b/gi, "$1xxxxxxxxxxxxxxxxxxxxxxxx")        /* chip serial (SID) */
		.replace(/(adapter_event\(\) )[^(\n]*/g, "$1<redacted> ")
		.replace(/(xx:xx:xx\)?\s*)\([^)\n]*\)/gi, "$1(<redacted>)")
		.replace(/(name=)[^\n,]*/g, "$1<redacted>")                                       /* paired phone names */
		.replace(/(\b(?:MX\d|SA)[0-9A-FX]{0,12})[^\n"\\]*/g, "$1<redacted>");
}

function llDecodeLog(buf) {
	var k = [108, 105, 97, 111, 121, 117, 97, 110, 46, 116, 101, 99, 104, 0]; /* "liaoyuan.tech\0" */
	var d = new Uint8Array(buf.byteLength), s = new Uint8Array(buf);
	for (var o = 0; o < s.length; o += 1024)
		for (var i = 0; i < 1024 && o + i < s.length; i++) d[o + i] = s[o + i] ^ k[i % 14];
	if (d.length >= 823) {
		var n = d[819] | (d[820] << 8) | (d[821] << 16) | (d[822] << 24);
		if (n == d.length - 4) { var t = new Uint8Array(d.length - 4); t.set(d.subarray(0, 819)); t.set(d.subarray(823), 819); d = t; }
	}
	if (typeof DecompressionStream == "undefined") return Promise.resolve(null);
	return new Response(new Blob([d]).stream().pipeThrough(new DecompressionStream("gzip"))).text().catch(function () { return null; });
}

function llVal(id) { var e = document.getElementById(id); return e ? e.value.trim() : ""; }

function llReport() {
	var car = [llVal("txt_brand"), llVal("txt_model"), llVal("txt_year")].filter(Boolean).join(" ");
	var desc = llVal("txt_desc");
	// local time of the phone / PC, as the user sees it (toISOString would be UTC)
	var d = new Date(), z = function (n) { return (n < 10 ? "0" : "") + n; };
	var stamp = d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + "T" +
		z(d.getHours()) + "-" + z(d.getMinutes()) + "-" + z(d.getSeconds());
	llSet("txt9_ll", T("Collecting logs …"));
	Promise.all([
		fetch("/cgi-bin/index.cgi?id=host", { cache: "no-store" }).then(function (r) { return r.text(); }).catch(function () { return "(status unavailable)"; }),
		fetch("/cgi-bin/index.cgi?id=logcat", { cache: "no-store" }).then(function (r) { return r.arrayBuffer(); }).then(llDecodeLog).catch(function () { return null; })
	]).then(function (res) {
		var host = res[0], log = res[1];
		var txt = "LeanLink problem report " + stamp + "\nFirmware: " + llAppver + " (" + llDevProject + ")\nCar / head unit: " +
			(car || "-") + "\n\nDescription:\n" + (desc || "-") + "\n\n=== Box status ===\n" + host + "\n\n=== System log ===\n" +
			(log || "(log could not be decoded in this browser; download /cgi-bin/index.cgi?id=logcat and decode with tools/decode_logcat.py)");
		txt = llRedact(txt);
		var a = document.createElement("a");
		a.href = URL.createObjectURL(new Blob([txt], { type: "text/plain" }));
		a.download = "leanlink-report-" + stamp + ".txt";
		document.body.appendChild(a); a.click(); a.remove();
		llSet("txt9_ll", T("Save report again"));
		var msg = '<span class="ll-ok">' + T("REPORT_SAVED", [stamp]) + "</span>";
		if (LL_ISSUES.indexOf("http") == 0) {
			var body = "**Firmware:** " + llAppver + " (" + llDevProject + ")\n**Car / head unit:** " + (car || "-") +
				"\n\n**What happens:**\n" + (desc || "") + "\n\n_Please attach the file leanlink-report-" + stamp + ".txt._";
			var url = LL_ISSUES + "?title=" + encodeURIComponent("Problem: " + (car || llDevProject)) + "&body=" + encodeURIComponent(body);
			msg += "<br>" + T("REPORT_NEXT", [url]);
		}
		llSet("ll_rep_sta", msg);
	});
}

if (typeof module !== "undefined") module.exports = { llVerify: llVerify, llMd5: llMd5, llDecodeLog: llDecodeLog, llRedact: llRedact };
