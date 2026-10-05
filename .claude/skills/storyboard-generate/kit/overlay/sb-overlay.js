/* Talking-head overlay timing (storyboard-generate kit). Every element with data-in="<sec>" enters
   at that time (slide toward its zone's side + fade); data-out="<sec>" leaves early; everything
   still on screen exits together 0.35s before the end. All legs are fromTo so a seeking renderer
   never pops.
     data-strike="<sec>"                       draws a .strike line (CSS var --s 0 -> 1)
     data-count="<to>" data-count-at="<sec>"   counts a number up [data-prefix data-suffix]
   Usage: const tl = SB_OV.build(duration); window.__timelines[id] = tl; */
window.SB_OV = {
  IN: 0.45, OUT: 0.3, EASE_IN: "power3.out", EASE_OUT: "power2.in", TAIL: 0.35,
  build(dur) {
    const tl = gsap.timeline({ paused: true });
    const end = dur - this.TAIL;
    document.querySelectorAll("[data-in]").forEach((el) => {
      // slide in from the side the element sits on: its own side-l/side-r wins over the zone's
      const side = el.closest(".side-l,.side-r,.zone");
      const cl = side ? side.classList : { contains: () => false };
      const dx = cl.contains("right") || cl.contains("side-r") ? 60 : cl.contains("left") || cl.contains("side-l") ? -60 : 0;
      const dy = dx === 0 ? 40 : 0;
      const t = parseFloat(el.dataset.in);
      tl.fromTo(el, { autoAlpha: 0, x: dx, y: dy }, { autoAlpha: 1, x: 0, y: 0, duration: this.IN, ease: this.EASE_IN }, t);
      const o = el.dataset.out ? parseFloat(el.dataset.out) : end;
      tl.fromTo(el, { autoAlpha: 1 }, { autoAlpha: 0, duration: this.OUT, ease: this.EASE_OUT, immediateRender: false }, o);
    });
    document.querySelectorAll("[data-strike]").forEach((el) => {
      tl.fromTo(el, { "--s": 0 }, { "--s": 1, duration: 0.5, ease: "power2.inOut" }, parseFloat(el.dataset.strike));
    });
    document.querySelectorAll("[data-count]").forEach((el) => {
      const to = parseFloat(el.dataset.count), at = parseFloat(el.dataset.countAt || el.dataset.in || 0);
      const pre = el.dataset.prefix || "", suf = el.dataset.suffix || "", o = { v: 0 };
      const fmt = (v) => pre + Math.round(v).toLocaleString("en-US") + suf;
      el.textContent = fmt(0);
      tl.fromTo(o, { v: 0 }, { v: to, duration: 1.2, ease: "power2.out", onUpdate: () => (el.textContent = fmt(o.v)) }, at);
    });
    tl.set({}, {}, dur);
    return tl;
  },
};
window.ACM_OV = window.SB_OV;   // name used by the first project that grew this kit
