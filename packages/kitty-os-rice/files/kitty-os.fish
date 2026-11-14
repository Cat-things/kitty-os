# kitty-os shell setup for every user. Your own ~/.config/fish/config.fish
# runs after this and can change any of it.

if status is-interactive
    # The greeting is a cat and a fact from the current cat mode.
    function fish_greeting
        if type -q catmode
            catmode greet
        end
    end

    if type -q starship
        starship init fish | source
    end

    abbr -a ll 'ls -lah'
    abbr -a fetch fastfetch
end
