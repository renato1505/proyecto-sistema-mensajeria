document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-updates-slider]").forEach(function (slider) {
        const items = Array.from(slider.querySelectorAll(".update-item"));
        const dotsWrap = slider.querySelector(".updates-dots");
        if (!items.length || !dotsWrap) return;

        items.forEach(function (_, index) {
            const dot = document.createElement("button");
            dot.type = "button";
            dot.setAttribute("aria-label", "Ver novedad " + (index + 1));
            dot.addEventListener("click", function () {
                activar(index);
            });
            dotsWrap.appendChild(dot);
        });

        const dots = Array.from(dotsWrap.querySelectorAll("button"));
        let actual = Math.max(0, items.findIndex(function (item) {
            return item.classList.contains("active");
        }));

        function activar(index) {
            actual = index;
            items.forEach(function (item, itemIndex) {
                item.classList.toggle("active", itemIndex === actual);
            });
            dots.forEach(function (dot, dotIndex) {
                dot.classList.toggle("active", dotIndex === actual);
            });
        }

        activar(actual);
        if (items.length > 1) {
            window.setInterval(function () {
                activar((actual + 1) % items.length);
            }, 4500);
        }
    });
});
