// Shows a friendly message while the free Render server wakes up from sleep.
// It watches every request to the API and shows a banner if one is slow.
(function () {
  var SLOW_MS = 3000;
  var banner = null;
  var pending = 0;
  var timer = null;

  function show() {
    if (banner) return;
    banner = document.createElement("div");
    banner.setAttribute("role", "status");
    banner.textContent =
      "Waking up the server. This can take up to a minute the first time. Please wait...";
    banner.style.cssText =
      "position:fixed;top:0;left:0;right:0;z-index:9999;padding:10px 16px;" +
      "text-align:center;background:#f5c542;color:#222;font:14px/1.4 system-ui,sans-serif;";
    (document.body || document.documentElement).appendChild(banner);
  }

  function hide() {
    if (banner) {
      banner.remove();
      banner = null;
    }
  }

  var realFetch = window.fetch;
  window.fetch = function (input) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.indexOf("onrender.com") === -1) {
      return realFetch.apply(this, arguments);
    }
    pending += 1;
    if (pending === 1) timer = setTimeout(show, SLOW_MS);

    var request = realFetch.apply(this, arguments);
    var done = function () {
      pending -= 1;
      if (pending === 0) {
        clearTimeout(timer);
        timer = null;
        hide();
      }
    };
    request.then(done, done);
    return request;
  };
})();