(require 'ox-publish)

; (setq org-html-htmlize-output-type nil)

(setq org-publish-project-alist
      '(
	("posts"
         :base-extension "org"
         :base-directory "notes/"
         :publishing-directory "html/"
         :publishing-function org-html-publish-to-html
         :recursive t
	 )
	("assets"
         :base-extension "css\\|png\\|jpg"
         :base-directory "notes/"
         :publishing-directory "html/"
         :publishing-function org-publish-attachment
         :recursive t
	 )
        ("all" :components ("posts" "assets"))))
