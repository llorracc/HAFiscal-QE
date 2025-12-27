;;; AucTeX-config.el --- Shared AucTeX configuration for HAFiscal project
;;; Commentary:
;; This file contains AucTeX settings optimized for the HAFiscal project.
;; It can be loaded by any .tex file using Local Variables:
;; % eval: (load (expand-file-name "@resources/emacs/AucTeX-config.el" (locate-dominating-file default-directory ".git")))

;;; Code:

;; Ensure AucTeX is loaded before configuring
(require 'tex nil t)

;; Enable PDF mode by default
(setq-local TeX-PDF-mode t)

;; Better error reporting and debugging
(setq-local TeX-file-line-error t)
(setq-local TeX-debug-warnings t)
(setq-local TeX-parse-all-errors t)

;; Enable source correlation (sync between source and PDF)
(setq-local TeX-source-correlate-mode t)

;; Auto-parse TeX files for macros and environments
(setq-local TeX-parse-self t)

;; Force BibTeX as the default bibliography processor (no prompting)
(setq-local LaTeX-biblatex-use-Biber nil)      ; Never use Biber
(setq-local TeX-command-default "LaTeX")        ; Default compile command
(setq-local TeX-command-BibTeX "BibTeX")        ; Use BibTeX, not Biber

;; Clean up and configure BibTeX commands for better reliability
(when (boundp 'TeX-command-list)
  (setq TeX-command-list (assq-delete-all (car (assoc "BibTeX" TeX-command-list)) TeX-command-list))
  (setq TeX-command-list (assq-delete-all (car (assoc "Biber" TeX-command-list)) TeX-command-list))  ; Remove Biber
  (add-to-list 'TeX-command-list '("BibTeX" "bibtex %s" TeX-run-BibTeX nil t :help "Run BibTeX") t))

;; Ensure bibliography backend selection doesn't prompt user
(setq-local TeX-engine 'default)                ; Use pdfTeX (not LuaTeX/XeTeX which might prefer biber)

;; Platform-specific PDF viewers with forward search support
(cond 
 ;; macOS: Use Skim with forward search and background opening
 ((string-equal system-type "darwin") 
  (setq TeX-view-program-list '(("Skim" "/Applications/Skim.app/Contents/SharedSupport/displayline -b %n %o %b"))))
 
 ;; Linux: Use Evince with forward search support
 ((string-equal system-type "gnu/linux")
  (setq TeX-view-program-list '(("Evince" "evince --page-index=%(outpage) %o")))
  (setq TeX-view-program-selection '((output-pdf "Evince")))))

;; Provide a message when loaded successfully
(message "HAFiscal AucTeX configuration loaded successfully")

;;; AucTeX-config.el ends here 