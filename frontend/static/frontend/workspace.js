// Keep the original submitter so decision buttons retain their name and value.
const confirmation = document.querySelector("#confirm-action");
let pendingForm;
let pendingButton;
document.addEventListener("submit", event => {
    const form = event.target;
    if (form.method.toLowerCase() !== "post") return;
    if (form.dataset.busy === "true") {
        event.preventDefault();
        return;
    }
    const question = event.submitter?.dataset.confirm || form.dataset.confirm;
    if (question && confirmation && !form.dataset.confirmed) {
        event.preventDefault();
        pendingForm = form;
        pendingButton = event.submitter;
        confirmation.querySelector("p").textContent = question;
        confirmation.showModal();
        return;
    }
    delete form.dataset.confirmed;
    form.dataset.busy = "true";
    form.setAttribute("aria-busy", "true");
});
confirmation?.querySelector("[data-proceed]").addEventListener("click", () => {
    confirmation.close();
    pendingForm.dataset.confirmed = "true";
    pendingForm.requestSubmit(pendingButton || undefined);
});
confirmation?.querySelector("[data-cancel]").addEventListener("click", () => confirmation.close());
window.addEventListener("pageshow", () => {
    document.querySelectorAll("form[data-busy]").forEach(form => {
        delete form.dataset.busy;
        form.removeAttribute("aria-busy");
    });
});
