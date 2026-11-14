# kitty-os ~/.bashrc

# Only for interactive shells.
[[ $- != *i* ]] && return

alias ls='ls --color=auto'
alias ll='ls -lah'
alias grep='grep --color=auto'
alias fetch='fastfetch'

HISTCONTROL=ignoreboth
HISTSIZE=5000
shopt -s histappend checkwinsize

if command -v starship >/dev/null; then
    eval "$(starship init bash)"
else
    PS1='\[\e[35m\]\w\[\e[0m\] 🐾 '
fi

# A cat and a fact from the current cat mode.
command -v catmode >/dev/null && catmode greet
