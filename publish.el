(require 'ox-publish)

; https://stackoverflow.com/questions/9742836/how-do-i-format-the-postamble-in-html-export-with-org-mode
(setq org-html-postamble "
<p>Updated: %C</p>
<p>Created: %d</p>
<p>Author: %a</p>
<p>Email: %e</p>
")


; https://emacs.stackexchange.com/questions/20731/setting-up-ditaa-in-org-mode
(setq org-ditaa-jar-path "~/project/lua51/tool/ditaa.jar")

(org-babel-lob-ingest "./book/lib.org")

(setq org-babel-lua-command "lua5.1")

(setq org-publish-project-alist
      '(
	("posts"
         :base-extension "org"
         :base-directory "book/"
         :publishing-directory "docs/"
         :publishing-function org-html-publish-to-html
         :recursive t
	 )
	("assets"
         :base-extension "css\\|png\\|jpg\\|ico"
         :base-directory "book/"
         :publishing-directory "docs/"
         :publishing-function org-publish-attachment
         :recursive t
	 )
        ("all" :components ("posts" "assets"))))

