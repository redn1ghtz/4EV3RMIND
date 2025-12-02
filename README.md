# 4EV3RMIND
4EV3RMIND

if grep -q "$REPO_URL" /etc/apt/sources.list; then
    echo "Repository already exists in sources.list"
else
    echo "Adding repository: $REPO_URL"
    echo "$REPO_URL" | sudo tee -a /etc/apt/sources.list
    echo "Repository added successfully"
fi


sudo apt update
sudo apt upgrade
