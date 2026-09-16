// Inline config to evitar requisições relativas quebradas em rotas aninhadas.
const POPUP_STYLES = `
#inline-editor-popup {
  width: 360px;
  position: fixed;
  z-index: 10000;
  background: #161718;
  color: white;
  border: 1px solid #4a5568;
  border-radius: 16px;
  padding: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  flex-direction: column;
  gap: 10px;
  display: none;
}

@media (max-width: 768px) {
  #inline-editor-popup {
    width: calc(100% - 20px);
  }
}

#inline-editor-popup.is-active {
  display: flex;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

#inline-editor-popup.is-disabled-view {
  padding: 10px 15px;
}

#inline-editor-popup textarea {
  height: 100px;
  padding: 4px 8px;
  background: transparent;
  color: white;
  font-family: inherit;
  font-size: 0.875rem;
  line-height: 1.42;
  resize: none;
  outline: none;
}

#inline-editor-popup .button-container {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

#inline-editor-popup .popup-button {
  border: none;
  padding: 6px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 700;
  height: 34px;
  outline: none;
}

#inline-editor-popup .save-button {
  background: #673de6;
  color: white;
}

#inline-editor-popup .cancel-button {
  background: transparent;
  border: 1px solid #3b3d4a;
  color: white;
}
`;

function getPopupHTMLTemplate(saveLabel, cancelLabel) {
  return `
    <textarea></textarea>
    <div class="button-container">
      <button class="popup-button cancel-button">${cancelLabel}</button>
      <button class="popup-button save-button">${saveLabel}</button>
    </div>
  `;
}

const PLUGIN_APPLY_EDIT_API_URL = '/api/apply-edit';

const ALLOWED_PARENT_ORIGINS = [
	'https://horizons.hostinger.com',
	'https://horizons.hostinger.dev',
	'https://horizons-frontend-local.hostinger.dev',
	'http://localhost:4000',
];

let popupElement = null;
let popupTextarea = null;
let popupSaveButton = null;
let popupCancelButton = null;
let currentEditingInfo = null;
let disabledTooltipElement = null;

let translations = {
  cancel: 'Cancel',
  save: 'Save',
  addText: 'Add text',
  disabledTooltipText: "This text can be changed only through chat."
};

let areStylesInjected = false;

let globalEventHandlers = null;

function injectPopupStyles() {
  if (areStylesInjected) return;

  const styleElement = document.createElement('style');
  styleElement.id = 'inline-editor-styles';
  styleElement.textContent = POPUP_STYLES;
  document.head.appendChild(styleElement);
  areStylesInjected = true;
}

function createPopup() {
  if (popupElement) return;

  injectPopupStyles();

  popupElement = document.createElement('div');
  popupElement.id = 'inline-editor-popup';
 
  popupElement.innerHTML = getPopupHTMLTemplate(translations.save, translations.cancel);
  document.body.appendChild(popupElement);
 
  popupTextarea = popupElement.querySelector('textarea');
  popupSaveButton = popupElement.querySelector('.save-button');
  popupCancelButton = popupElement.querySelector('.cancel-button');

  popupTextarea.placeholder = `${translations.addText}...`;
 
  popupSaveButton.addEventListener('click', handlePopupSave);
  popupCancelButton.addEventListener('click', handlePopupCancel);
}

function showPopup(targetElement, editId, currentText) {
  if (!popupElement) createPopup();

  currentEditingInfo = { editId, targetElement };

  popupSaveButton.textContent = translations.save;
  popupCancelButton.textContent = translations.cancel;

  popupTextarea.style.display = 'block';
  popupTextarea.value = currentText;
  popupTextarea.disabled = false;
  popupSaveButton.style.display = 'inline-block';

  popupElement.classList.add('is-active');
  popupTextarea.focus();

 const parentOrigin = getParentOrigin();
 if (parentOrigin && ALLOWED_PARENT_ORIGINS.includes(parentOrigin)) {
   window.parent.postMessage({
     type: 'editEnter',
   }, parentOrigin);
 }
}

function hidePopup() {
  if (popupElement) {
    popupElement.classList.remove('is-active');
    popupElement.classList.remove('is-disabled-view');
   
    if(popupTextarea) popupTextarea.style.display = 'none';
    if(popupSaveButton) popupSaveButton.style.display = 'none';
  }
  currentEditingInfo = null;
}

function handleGlobalEvent(event) {
  if (!document.getElementById('root')?.getAttribute('data-edit-mode-enabled')) {
    return;
  }

  if (event.target.closest('#inline-editor-popup')) {
    return;
  }

  const editableElement = event.target.closest('[data-edit-id]');

  if (editableElement) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    if (event.type === 'click') {
      if (currentEditingInfo) {
        hidePopup();
      }

      const editId = editableElement.getAttribute('data-edit-id');
      if (!editId) {
        console.warn('[INLINE EDITOR] Clicked element missing data-edit-id');
        return;
      }

      const currentText = editableElement.textContent || '';
      showPopup(editableElement, editId, currentText);
    }
  } else {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }
}

function getParentOrigin() {
  if (window.location.ancestorOrigins && window.location.ancestorOrigins.length > 0) {
    return window.location.ancestorOrigins[0];
  }
  
  if (document.referrer) {
    try {
      return new URL(document.referrer).origin;
    } catch (e) {
      console.warn('Invalid referrer URL:', document.referrer);
    }
  }
  
  return null;
}

async function handlePopupSave() {
  if (!currentEditingInfo) return;
  
  const newText = popupTextarea.value
  // Replacing characters that cause Babel parser to crash
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/{/g, '&#123;')
    .replace(/}/g, '&#125;')

  const { editId } = currentEditingInfo;

  try {
    const response = await fetch(PLUGIN_APPLY_EDIT_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        editId: editId,
        newFullText: newText
      }),
    });

    const result = await response.json();
    if (result.success) {
      const parentOrigin = getParentOrigin();
      if (parentOrigin && ALLOWED_PARENT_ORIGINS.includes(parentOrigin)) {
        window.parent.postMessage({
          type: 'editApplied',
          payload: {
            editId: editId,
            fileContent: result.newFileContent,
            beforeCode: result.beforeCode,
            afterCode: result.afterCode,
          }
        }, parentOrigin);
      } else {
        console.error('Unauthorized parent origin:', parentOrigin);
      }
    } else {
      console.error(`[vite][visual-editor] Error saving changes: ${result.error}`);
    }
  } catch (error) {
    console.error(`[vite][visual-editor] Error during fetch for ${editId}:`, error);
  }

  hidePopup();
}

function handlePopupCancel() {
 const parentOrigin = getParentOrigin();
 if (parentOrigin && ALLOWED_PARENT_ORIGINS.includes(parentOrigin)) {
   window.parent.postMessage({
     type: 'editCancel',
   }, parentOrigin);
 }

  hidePopup();
}

function createDisabledTooltip() {
  if (disabledTooltipElement) return;

  disabledTooltipElement = document.createElement('div');
  disabledTooltipElement.id = 'inline-editor-disabled-tooltip';
  document.body.appendChild(disabledTooltipElement);
}

function showDisabledTooltip(targetElement) {
  if (!disabledTooltipElement) createDisabledTooltip();

  disabledTooltipElement.textContent = translations.disabledTooltipText;
  
  if (!disabledTooltipElement.isConnected) {
    document.body.appendChild(disabledTooltipElement);
  }
  disabledTooltipElement.classList.add('tooltip-active');

  const tooltipWidth = disabledTooltipElement.offsetWidth;
  const tooltipHeight = disabledTooltipElement.offsetHeight;
  const rect = targetElement.getBoundingClientRect();

  // Ensures that tooltip is not off the screen with 5px margin
  let newLeft = rect.left + window.scrollX + (rect.width / 2) - (tooltipWidth / 2);
  let newTop = rect.bottom + window.scrollY + 5;

  if (newLeft < window.scrollX) {
    newLeft = window.scrollX + 5; 
  }
  if (newLeft + tooltipWidth > window.innerWidth + window.scrollX) {
    newLeft = window.innerWidth + window.scrollX - tooltipWidth - 5; 
  }
  if (newTop + tooltipHeight > window.innerHeight + window.scrollY) {
    newTop = rect.top + window.scrollY - tooltipHeight - 5; 
  }
  if (newTop < window.scrollY) {
    newTop = window.scrollY + 5; 
  }

  disabledTooltipElement.style.left = `${newLeft}px`;
  disabledTooltipElement.style.top = `${newTop}px`;
}

function hideDisabledTooltip() {
  if (disabledTooltipElement) {
    disabledTooltipElement.classList.remove('tooltip-active');
  }
}

function handleDisabledElementHover(event) {
  showDisabledTooltip(event.currentTarget);
}

function handleDisabledElementLeave() {
  hideDisabledTooltip();
}

function enableEditMode() {
  document.getElementById('root')?.setAttribute('data-edit-mode-enabled', 'true');
  
  injectPopupStyles(); 
  
  if (!globalEventHandlers) {
    globalEventHandlers = {
      mousedown: handleGlobalEvent,
      pointerdown: handleGlobalEvent,
      click: handleGlobalEvent
    };
    
    Object.entries(globalEventHandlers).forEach(([eventType, handler]) => {
      document.addEventListener(eventType, handler, true);
    });
  }
  
  document.querySelectorAll('[data-edit-disabled]').forEach(el => {
    el.removeEventListener('mouseenter', handleDisabledElementHover);
    el.addEventListener('mouseenter', handleDisabledElementHover);
    el.removeEventListener('mouseleave', handleDisabledElementLeave);
    el.addEventListener('mouseleave', handleDisabledElementLeave);
  });
}

function disableEditMode() {
  document.getElementById('root')?.removeAttribute('data-edit-mode-enabled');

  hidePopup();
  hideDisabledTooltip();

  if (globalEventHandlers) {
    Object.entries(globalEventHandlers).forEach(([eventType, handler]) => {
      document.removeEventListener(eventType, handler, true);
    });
    globalEventHandlers = null;
  }
  
  document.querySelectorAll('[data-edit-disabled]').forEach(el => {
    el.removeEventListener('mouseenter', handleDisabledElementHover);
    el.removeEventListener('mouseleave', handleDisabledElementLeave);
  });
}

window.addEventListener("message", function(event) {
  if (event.data?.type === "enable-edit-mode") {
    if (event.data?.translations) {
        translations = { ...translations, ...event.data.translations };
    }
    enableEditMode();
  }
  if (event.data?.type === "disable-edit-mode") {
    disableEditMode();
  }
}); 
