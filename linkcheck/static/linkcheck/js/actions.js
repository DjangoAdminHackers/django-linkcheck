window.addEventListener("load", function () {
  const changeListForm = document.getElementById("changelist-form");
  const actionButtons = Array.from(document.querySelectorAll(".field-list_actions > a"));
  actionButtons.forEach((button) =>
    button.addEventListener("click", ({ target }) => {
      const action = changeListForm.querySelector("select[name='action']");
      const currentCheckbox = target.closest("tr").querySelector(".action-select");
      const allCheckboxes = Array.from(
        changeListForm.querySelectorAll('input[type="checkbox"].action-select:checked')
      );
      action.value = target.getAttribute("data-action");
      allCheckboxes.forEach((checkbox) => {
        checkbox.checked = false;
      });
      currentCheckbox.checked = true;
      changeListForm.submit();
    })
  );
});
